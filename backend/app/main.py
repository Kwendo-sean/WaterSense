import os, uuid, csv, io, time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query, Request, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc, func
from sqlalchemy.exc import IntegrityError
from .core import Base, engine, SessionLocal
from .models import Station, TelemetryReading, RiskAssessment, Alert, Forecast, PumpEvent, SurveyResponse
from .schemas import TelemetryIn, StationIn, StationPatch, SurveyIn
from .services.risk import assess_risk
from .services.forecast import calculate_forecast
from .services.pump import evaluate_pump, predict_pump_schedule
from .seed import seed_database
from .simulator import simulator


def iso(value):
    if value is None: return None
    if isinstance(value, datetime): return value.replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')
    return value

def station_dict(s):
    return {"id":s.id,"station_code":s.station_code,"name":s.name,"description":s.description,"station_type":s.station_type,"latitude":s.latitude,"longitude":s.longitude,"location_text":s.location_text,"status":s.status,"installed_at":iso(s.installed_at),"last_seen_at":iso(s.last_seen_at),"source_type":s.source_type,"created_at":iso(s.created_at),"updated_at":iso(s.updated_at),"pump_status":s.pump_status,"pump_capacity_liters":s.pump_capacity_liters}

def pump_event_dict(e):
    return {"id":e.id,"station_id":e.station_id,"triggered_at":iso(e.triggered_at),"trigger_level":e.trigger_level,"stopped_at":iso(e.stopped_at),"stop_level":e.stop_level,"volume_liters":e.volume_liters}

def reading_dict(r):
    return {"id":r.id,"station_id":r.station_id,"timestamp":iso(r.timestamp),"ph":r.ph,"turbidity_ntu":r.turbidity_ntu,"temperature_c":r.temperature_c,"conductivity_us_cm":r.conductivity_us_cm,"tds_ppm":r.tds_ppm,"water_level_percent":r.water_level_percent,"flow_rate_l_min":r.flow_rate_l_min,"battery_percent":r.battery_percent,"signal_strength":r.signal_strength,"source":r.source}

def risk_dict(r):
    return {"id":r.id,"station_id":r.station_id,"reading_id":r.reading_id,"timestamp":iso(r.timestamp),"overall_risk_score":r.overall_risk_score,"risk_level":r.risk_level,"ph_score":r.ph_score,"turbidity_score":r.turbidity_score,"conductivity_score":r.conductivity_score,"water_level_score":r.water_level_score,"anomaly_score":r.anomaly_score,"detected_factors":r.detected_factors,"explanation":r.explanation,"recommended_action":r.recommended_action,"confidence":r.confidence,"model_version":r.model_version}

def alert_dict(a):
    return {"id":a.id,"station_id":a.station_id,"created_at":iso(a.created_at),"updated_at":iso(a.updated_at),"resolved_at":iso(a.resolved_at),"severity":a.severity,"type":a.type,"title":a.title,"message":a.message,"recommended_action":a.recommended_action,"acknowledged":a.acknowledged,"resolved":a.resolved}

class ConnectionManager:
    def __init__(self): self.connections=[]
    async def connect(self,ws): await ws.accept();self.connections.append(ws)
    def disconnect(self,ws):
        if ws in self.connections:self.connections.remove(ws)
    async def broadcast(self,event,data):
        dead=[]
        for ws in self.connections:
            try: await ws.send_json({"event":event,"data":data})
            except Exception:dead.append(ws)
        for ws in dead:self.disconnect(ws)
manager=ConnectionManager()

async def ingest_payload(payload: dict[str,Any]):
    data=TelemetryIn.model_validate(payload);db=SessionLocal()
    try:
        station=db.scalar(select(Station).where(Station.station_code==data.station_code))
        if not station: raise HTTPException(404,"Unknown station")
        metrics=data.metrics.model_dump(); history_rows=db.scalars(select(TelemetryReading).where(TelemetryReading.station_id==station.id).order_by(desc(TelemetryReading.timestamp)).limit(100)).all()
        history=[{k:getattr(r,k) for k in metrics} for r in reversed(history_rows)]
        previous=station.status
        reading=TelemetryReading(station_id=station.id,timestamp=(data.timestamp or datetime.now(timezone.utc)).replace(tzinfo=None),source=data.device.source,battery_percent=data.device.battery_percent,signal_strength=data.device.signal_strength,raw_payload=data.model_dump(mode="json"),**metrics)
        db.add(reading);db.flush();result=assess_risk(metrics,history)
        assessment=RiskAssessment(station_id=station.id,reading_id=reading.id,**result);db.add(assessment)
        station.status=result["risk_level"];station.last_seen_at=reading.timestamp
        alert=None
        if result["risk_level"] in ("warning","critical"):
            alert=db.scalar(select(Alert).where(Alert.station_id==station.id,Alert.resolved==False,Alert.severity==result["risk_level"]))
            if not alert:
                alert=Alert(station_id=station.id,severity=result["risk_level"],type="water_quality",title=f"{result['risk_level'].title()} telemetry risk",message=result["explanation"],recommended_action=result["recommended_action"]);db.add(alert);db.flush()
        if metrics.get("water_level_percent") is not None:
            levels=[(r.timestamp,r.water_level_percent) for r in reversed(history_rows[:30]) if r.water_level_percent is not None]+[(reading.timestamp,metrics["water_level_percent"])]
            forecast=calculate_forecast(levels)
            if forecast:
                metadata={**forecast,"forecast_for":forecast["forecast_for"].isoformat()}
                db.add(Forecast(station_id=station.id,forecast_for=forecast["forecast_for"],predicted_value=15,confidence=forecast["confidence"],forecast_metadata=metadata))
        pump_changed=None
        if metrics.get("water_level_percent") is not None:
            new_pump_status,action=evaluate_pump(station.pump_status,metrics["water_level_percent"],station.pump_capacity_liters)
            if action:
                if action[0]=="start":
                    db.add(PumpEvent(station_id=station.id,triggered_at=reading.timestamp,trigger_level=action[1]))
                elif action[0]=="stop":
                    open_event=db.scalar(select(PumpEvent).where(PumpEvent.station_id==station.id,PumpEvent.stopped_at.is_(None)).order_by(desc(PumpEvent.triggered_at)))
                    if open_event: open_event.stopped_at=reading.timestamp;open_event.stop_level=action[2];open_event.volume_liters=action[3]
                station.pump_status=new_pump_status
                pump_changed={"station_id":station.id,"station_code":station.station_code,"pump_status":new_pump_status,"water_level_percent":metrics["water_level_percent"],"timestamp":iso(reading.timestamp)}
        db.commit()
        rd=reading_dict(reading);ra=risk_dict(assessment);sd=station_dict(station)
    finally: db.close()
    await manager.broadcast("telemetry:new",{"station":sd,"reading":rd,"risk":ra})
    await manager.broadcast("risk:new",ra)
    if previous!=result["risk_level"]: await manager.broadcast("station:status_changed",{"station_id":station.id,"station_code":station.station_code,"previous":previous,"current":result["risk_level"],"risk_score":result["overall_risk_score"],"timestamp":iso(reading.timestamp)})
    if pump_changed: await manager.broadcast("pump:changed",pump_changed)
    if alert: await manager.broadcast("alert:new",alert_dict(alert))
    return {"accepted":True,"reading_id":reading.id,"station_status":result["risk_level"],"risk_score":result["overall_risk_score"],"assessment_id":assessment.id}

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine);seed_database();simulator.ingest=ingest_payload
    if os.getenv("SIMULATOR_ENABLED","true").lower()=="true": await simulator.start()
    yield
    await simulator.stop()

app=FastAPI(title="WaterSense AI API",version="1.0.0",lifespan=lifespan)
origins=os.getenv("CORS_ORIGINS","http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

# Shared operator password gating the dashboard, station views and simulator
# controls (same key used for the survey admin pages). No user accounts exist
# yet, so this is a single shared secret, not per-user auth.
ADMIN_KEY=os.getenv("SURVEY_ADMIN_KEY","")
def require_admin(x_admin_key:str|None=Header(None)):
    if not ADMIN_KEY or x_admin_key!=ADMIN_KEY:
        raise HTTPException(401,"Unauthorized")

@app.get("/api/v1/health")
def health(): return {"status":"healthy","service":"watersense-api","simulator":simulator.running}

@app.get("/api/v1/stations")
def stations(_:None=Depends(require_admin)):
    with SessionLocal() as db:return [station_dict(x) for x in db.scalars(select(Station).order_by(Station.station_code)).all()]

@app.post("/api/v1/stations",status_code=201)
def create_station(data:StationIn,_:None=Depends(require_admin)):
    with SessionLocal() as db:
        item=Station(**data.model_dump());db.add(item)
        try:db.commit()
        except IntegrityError:raise HTTPException(409,"Station code already exists")
        return station_dict(item)

@app.get("/api/v1/stations/{station_id}")
def get_station(station_id:int,_:None=Depends(require_admin)):
    with SessionLocal() as db:
        item=db.get(Station,station_id)
        if not item:raise HTTPException(404,"Station not found")
        return station_dict(item)

@app.patch("/api/v1/stations/{station_id}")
def patch_station(station_id:int,data:StationPatch,_:None=Depends(require_admin)):
    with SessionLocal() as db:
        item=db.get(Station,station_id)
        if not item:raise HTTPException(404,"Station not found")
        for k,v in data.model_dump(exclude_none=True).items():setattr(item,k,v)
        db.commit();return station_dict(item)

@app.post("/api/v1/telemetry")
async def telemetry(data:TelemetryIn):return await ingest_payload(data.model_dump())

@app.get("/api/v1/stations/{station_id}/telemetry")
def telemetry_history(station_id:int,limit:int=Query(100,ge=1,le=2000),_:None=Depends(require_admin)):
    with SessionLocal() as db:
        if not db.get(Station,station_id):raise HTTPException(404,"Station not found")
        rows=db.scalars(select(TelemetryReading).where(TelemetryReading.station_id==station_id).order_by(desc(TelemetryReading.timestamp)).limit(limit)).all()
        return [reading_dict(x) for x in reversed(rows)]

@app.get("/api/v1/stations/{station_id}/latest")
def latest(station_id:int,_:None=Depends(require_admin)):
    with SessionLocal() as db:
        station=db.get(Station,station_id)
        if not station:raise HTTPException(404,"Station not found")
        reading=db.scalar(select(TelemetryReading).where(TelemetryReading.station_id==station_id).order_by(desc(TelemetryReading.timestamp)))
        risk=db.scalar(select(RiskAssessment).where(RiskAssessment.station_id==station_id).order_by(desc(RiskAssessment.timestamp)))
        return {"station":station_dict(station),"reading":reading_dict(reading) if reading else None,"risk":risk_dict(risk) if risk else None}

@app.get("/api/v1/stations/{station_id}/risk")
def station_risk(station_id:int,limit:int=Query(100,ge=1,le=1000),_:None=Depends(require_admin)):
    with SessionLocal() as db:return [risk_dict(x) for x in reversed(db.scalars(select(RiskAssessment).where(RiskAssessment.station_id==station_id).order_by(desc(RiskAssessment.timestamp)).limit(limit)).all())]

@app.get("/api/v1/stations/{station_id}/forecast")
def station_forecast(station_id:int,_:None=Depends(require_admin)):
    with SessionLocal() as db:
        row=db.scalar(select(Forecast).where(Forecast.station_id==station_id).order_by(desc(Forecast.created_at)))
        if not row:return {"available":False,"reason":"Insufficient declining water-level history"}
        return {"available":True,"id":row.id,"station_id":row.station_id,"forecast_for":iso(row.forecast_for),"predicted_value":row.predicted_value,"confidence":row.confidence,"metadata":row.forecast_metadata}

@app.get("/api/v1/stations/{station_id}/pump")
def station_pump(station_id:int,_:None=Depends(require_admin)):
    with SessionLocal() as db:
        station=db.get(Station,station_id)
        if not station:raise HTTPException(404,"Station not found")
        events=db.scalars(select(PumpEvent).where(PumpEvent.station_id==station_id,PumpEvent.stopped_at.is_not(None)).order_by(desc(PumpEvent.triggered_at)).limit(60)).all()
        prediction=predict_pump_schedule([{"triggered_at":e.triggered_at,"volume_liters":e.volume_liters} for e in events])
        total_volume_liters=db.scalar(select(func.sum(PumpEvent.volume_liters)).where(PumpEvent.station_id==station_id,PumpEvent.stopped_at.is_not(None))) or 0.0
        total_cycles=db.scalar(select(func.count()).select_from(PumpEvent).where(PumpEvent.station_id==station_id,PumpEvent.stopped_at.is_not(None))) or 0
        return {"station_id":station.id,"pump_status":station.pump_status,"capacity_liters":station.pump_capacity_liters,"recent_events":[pump_event_dict(e) for e in events[:10]],"prediction":prediction,"total_volume_liters":round(total_volume_liters,1),"total_cycles":total_cycles}

@app.get("/api/v1/alerts")
def alerts(resolved:bool|None=None,_:None=Depends(require_admin)):
    with SessionLocal() as db:
        q=select(Alert).order_by(desc(Alert.created_at))
        if resolved is not None:q=q.where(Alert.resolved==resolved)
        return [alert_dict(x) for x in db.scalars(q).all()]

@app.patch("/api/v1/alerts/{alert_id}/acknowledge")
async def acknowledge(alert_id:int,_:None=Depends(require_admin)):
    with SessionLocal() as db:
        item=db.get(Alert,alert_id)
        if not item:raise HTTPException(404,"Alert not found")
        item.acknowledged=True;db.commit();return alert_dict(item)

@app.patch("/api/v1/alerts/{alert_id}/resolve")
async def resolve(alert_id:int,_:None=Depends(require_admin)):
    with SessionLocal() as db:
        item=db.get(Alert,alert_id)
        if not item:raise HTTPException(404,"Alert not found")
        item.resolved=True;item.resolved_at=datetime.now(timezone.utc).replace(tzinfo=None);db.commit();out=alert_dict(item)
    await manager.broadcast("alert:resolved",out);return out

@app.get("/api/v1/dashboard/summary")
def dashboard_summary(_:None=Depends(require_admin)):
    with SessionLocal() as db:
        sts=db.scalars(select(Station)).all();counts={k:sum(s.status==k for s in sts) for k in ("safe","watch","warning","critical")}
        readings=[]
        for s in sts:
            r=db.scalar(select(TelemetryReading).where(TelemetryReading.station_id==s.id).order_by(desc(TelemetryReading.timestamp)))
            if r:readings.append(r)
        active=db.scalar(select(func.count()).select_from(Alert).where(Alert.resolved==False)) or 0
        risk_penalty=counts["watch"]*5+counts["warning"]*12+counts["critical"]*24
        avg=lambda key:round(sum(getattr(r,key) for r in readings if getattr(r,key) is not None)/max(1,sum(getattr(r,key) is not None for r in readings)),1)
        return {"network_health":max(0,100-risk_penalty),"stations":len(sts),"status_counts":counts,"avg_ph":avg("ph"),"avg_turbidity":avg("turbidity_ntu"),"water_availability":avg("water_level_percent"),"active_alerts":active,"readings_processed":db.scalar(select(func.count()).select_from(TelemetryReading))}

@app.get("/api/v1/dashboard/pumps")
def dashboard_pumps(_:None=Depends(require_admin)):
    with SessionLocal() as db:
        stations=db.scalars(select(Station).where(Station.station_type=="tank").order_by(Station.station_code)).all()
        out=[]
        for s in stations:
            events=db.scalars(select(PumpEvent).where(PumpEvent.station_id==s.id,PumpEvent.stopped_at.is_not(None)).order_by(desc(PumpEvent.triggered_at)).limit(60)).all()
            prediction=predict_pump_schedule([{"triggered_at":e.triggered_at,"volume_liters":e.volume_liters} for e in events])
            out.append({"station_id":s.id,"station_code":s.station_code,"name":s.name,"pump_status":s.pump_status,"capacity_liters":s.pump_capacity_liters,"prediction":prediction})
        return out

@app.get("/api/v1/dashboard/activity")
def activity(limit:int=20,_:None=Depends(require_admin)):
    with SessionLocal() as db:
        rows=db.scalars(select(RiskAssessment).order_by(desc(RiskAssessment.timestamp)).limit(limit)).all()
        stations={s.id:s for s in db.scalars(select(Station)).all()}
        return [{"id":r.id,"timestamp":iso(r.timestamp),"station_id":r.station_id,"station_code":stations[r.station_id].station_code,"station_name":stations[r.station_id].name,"risk_level":r.risk_level,"risk_score":r.overall_risk_score,"message":r.detected_factors[0] if r.detected_factors else "Telemetry stable"} for r in rows]

@app.post("/api/v1/simulator/start")
async def start_simulator(_:None=Depends(require_admin)):await simulator.start();return {"running":simulator.running,"interval_seconds":simulator.interval}
@app.post("/api/v1/simulator/stop")
async def stop_simulator(_:None=Depends(require_admin)):await simulator.stop();return {"running":simulator.running}
@app.get("/api/v1/simulator/status")
def simulator_status(_:None=Depends(require_admin)):return {"running":simulator.running,"interval_seconds":simulator.interval,"scenarios":simulator.scenarios}
@app.post("/api/v1/simulator/scenario")
def scenario(payload:dict,_:None=Depends(require_admin)):
    station_id=payload.get("station_id");scenario_name=payload.get("scenario","NORMAL")
    if not station_id:raise HTTPException(422,"station_id is required")
    with SessionLocal() as db:
        if not db.get(Station,int(station_id)):raise HTTPException(404,"Station not found")
    simulator.set_scenario(station_id,scenario_name,payload.get("intensity",1),payload.get("overrides"));return {"accepted":True,"station_id":station_id,"scenario":scenario_name.upper()}

# -------- Market research survey --------
SURVEY_RATE_LIMIT=5          # max submissions
SURVEY_RATE_WINDOW=3600.0    # per hour, per IP, in-memory (single-process app)
_survey_submit_times:dict[str,list[float]]=defaultdict(list)

def survey_dict(r):
    return {"id":r.id,"submitted_at":iso(r.submitted_at),"location":r.location,"residence_type":r.residence_type,"water_source":r.water_source,"has_tank":r.has_tank,"has_pump":r.has_pump,"pump_control":r.pump_control,"problems":r.problems,"problem_frequency":r.problem_frequency,"auto_control_usefulness":r.auto_control_usefulness,"desired_features":r.desired_features,"purchase_intent":r.purchase_intent,"price_range":r.price_range,"main_concern":r.main_concern,"other_comments":r.other_comments}

def _tally(rows,field,denom=None):
    d=denom if denom is not None else len(rows);c:dict[str,int]={}
    for r in rows:
        v=getattr(r,field)
        if v is not None:c[v]=c.get(v,0)+1
    return [{"option":k,"count":v,"pct":round(v/d*100,1) if d else 0.0} for k,v in sorted(c.items(),key=lambda kv:-kv[1])]

def _tally_multi(rows,field,denom=None):
    d=denom if denom is not None else len(rows);c:dict[str,int]={}
    for r in rows:
        for v in (getattr(r,field) or []):c[v]=c.get(v,0)+1
    return [{"option":k,"count":v,"pct":round(v/d*100,1) if d else 0.0} for k,v in sorted(c.items(),key=lambda kv:-kv[1])]

@app.post("/api/v1/survey/responses",status_code=201)
def submit_survey(data:SurveyIn,request:Request):
    client_ip=request.client.host if request.client else "unknown"
    now_ts=time.time()
    window=[t for t in _survey_submit_times[client_ip] if now_ts-t<SURVEY_RATE_WINDOW]
    if len(window)>=SURVEY_RATE_LIMIT:
        raise HTTPException(429,"Too many submissions from this location. Please try again later.")
    with SessionLocal() as db:
        existing=db.scalar(select(SurveyResponse).where(SurveyResponse.idempotency_key==data.idempotency_key))
        if existing:return {"id":existing.id,"duplicate":True}
        row=SurveyResponse(id=uuid.uuid4().hex,**data.model_dump())
        db.add(row)
        try:db.commit()
        except IntegrityError:
            db.rollback()
            existing=db.scalar(select(SurveyResponse).where(SurveyResponse.idempotency_key==data.idempotency_key))
            if existing:return {"id":existing.id,"duplicate":True}
            raise HTTPException(409,"Duplicate submission")
    window.append(now_ts);_survey_submit_times[client_ip]=window
    return {"id":row.id,"duplicate":False}

@app.get("/api/v1/survey/results")
def survey_results(_:None=Depends(require_admin)):
    with SessionLocal() as db:
        rows=db.scalars(select(SurveyResponse)).all()
    total=len(rows)
    kenya=[r for r in rows if r.location in ("Nairobi","Another part of Kenya")]
    tank_rows=[r for r in rows if r.has_tank=="Yes"]
    pump_rows=[r for r in rows if r.has_pump=="Yes"]
    timestamps=[r.submitted_at for r in rows]
    return {
        "total_responses":total,
        "collection_start":iso(min(timestamps)) if timestamps else None,
        "collection_end":iso(max(timestamps)) if timestamps else None,
        "segments":{"all":total,"kenya":len(kenya),"with_tank":len(tank_rows),"with_pump":len(pump_rows)},
        "by_location":_tally(rows,"location"),
        "by_residence_type":_tally(rows,"residence_type"),
        "by_water_source":_tally(rows,"water_source"),
        "has_tank":_tally(rows,"has_tank"),
        "has_pump":_tally(rows,"has_pump"),
        "pump_control":_tally(pump_rows,"pump_control",denom=len(pump_rows)),
        "problems":_tally_multi(rows,"problems"),
        "problem_frequency":_tally(rows,"problem_frequency"),
        "auto_control_usefulness":_tally(rows,"auto_control_usefulness"),
        "desired_features":_tally_multi(rows,"desired_features"),
        "purchase_intent":_tally(rows,"purchase_intent"),
        "price_range":_tally(rows,"price_range"),
        "main_concern":_tally(rows,"main_concern"),
        "comments":[r.other_comments for r in rows if r.other_comments],
        "methodology_note":"Responses are self-reported and collected by convenience sampling (shared links), not a random or representative sample. Percentages for multi-select questions (problems, desired_features) can sum to more than 100% since respondents may pick several options. Pump-control percentages are calculated only among respondents who reported using an electric pump.",
    }

@app.get("/api/v1/survey/export")
def survey_export(_:None=Depends(require_admin)):
    with SessionLocal() as db:
        rows=db.scalars(select(SurveyResponse).order_by(SurveyResponse.submitted_at)).all()
    buf=io.StringIO();w=csv.writer(buf)
    fields=["id","submitted_at","location","residence_type","water_source","has_tank","has_pump","pump_control","problems","problem_frequency","auto_control_usefulness","desired_features","purchase_intent","price_range","main_concern","other_comments"]
    w.writerow(fields)
    for r in rows:
        w.writerow([r.id,iso(r.submitted_at),r.location,r.residence_type,r.water_source,r.has_tank,r.has_pump,r.pump_control or "","|".join(r.problems or []),r.problem_frequency,r.auto_control_usefulness,"|".join(r.desired_features or []),r.purchase_intent,r.price_range,r.main_concern,(r.other_comments or "").replace("\n"," ").replace("\r","")])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=watersense_survey_export.csv"})

@app.websocket("/ws/live")
async def live(ws:WebSocket):
    if not ADMIN_KEY or ws.query_params.get("key")!=ADMIN_KEY:
        await ws.close(code=4401);return
    await manager.connect(ws)
    try:
        while True:await ws.receive_text()
    except WebSocketDisconnect:manager.disconnect(ws)
