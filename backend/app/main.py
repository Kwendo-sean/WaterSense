import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, desc, func
from sqlalchemy.exc import IntegrityError
from .core import Base, engine, SessionLocal
from .models import Station, TelemetryReading, RiskAssessment, Alert, Forecast
from .schemas import TelemetryIn, StationIn, StationPatch
from .services.risk import assess_risk
from .services.forecast import calculate_forecast
from .seed import seed_database
from .simulator import simulator


def iso(value):
    if value is None: return None
    if isinstance(value, datetime): return value.replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')
    return value

def station_dict(s):
    return {"id":s.id,"station_code":s.station_code,"name":s.name,"description":s.description,"station_type":s.station_type,"latitude":s.latitude,"longitude":s.longitude,"location_text":s.location_text,"status":s.status,"installed_at":iso(s.installed_at),"last_seen_at":iso(s.last_seen_at),"source_type":s.source_type,"created_at":iso(s.created_at),"updated_at":iso(s.updated_at)}

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
        db.commit()
        rd=reading_dict(reading);ra=risk_dict(assessment)
    finally: db.close()
    await manager.broadcast("telemetry:new",{"station":station_dict(station),"reading":rd,"risk":ra})
    await manager.broadcast("risk:new",ra)
    if previous!=result["risk_level"]: await manager.broadcast("station:status_changed",{"station_id":station.id,"station_code":station.station_code,"previous":previous,"current":result["risk_level"],"risk_score":result["overall_risk_score"],"timestamp":iso(reading.timestamp)})
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

@app.get("/api/v1/health")
def health(): return {"status":"healthy","service":"watersense-api","simulator":simulator.running}

@app.get("/api/v1/stations")
def stations():
    with SessionLocal() as db:return [station_dict(x) for x in db.scalars(select(Station).order_by(Station.station_code)).all()]

@app.post("/api/v1/stations",status_code=201)
def create_station(data:StationIn):
    with SessionLocal() as db:
        item=Station(**data.model_dump());db.add(item)
        try:db.commit()
        except IntegrityError:raise HTTPException(409,"Station code already exists")
        return station_dict(item)

@app.get("/api/v1/stations/{station_id}")
def get_station(station_id:int):
    with SessionLocal() as db:
        item=db.get(Station,station_id)
        if not item:raise HTTPException(404,"Station not found")
        return station_dict(item)

@app.patch("/api/v1/stations/{station_id}")
def patch_station(station_id:int,data:StationPatch):
    with SessionLocal() as db:
        item=db.get(Station,station_id)
        if not item:raise HTTPException(404,"Station not found")
        for k,v in data.model_dump(exclude_none=True).items():setattr(item,k,v)
        db.commit();return station_dict(item)

@app.post("/api/v1/telemetry")
async def telemetry(data:TelemetryIn):return await ingest_payload(data.model_dump())

@app.get("/api/v1/stations/{station_id}/telemetry")
def telemetry_history(station_id:int,limit:int=Query(100,ge=1,le=2000)):
    with SessionLocal() as db:
        if not db.get(Station,station_id):raise HTTPException(404,"Station not found")
        rows=db.scalars(select(TelemetryReading).where(TelemetryReading.station_id==station_id).order_by(desc(TelemetryReading.timestamp)).limit(limit)).all()
        return [reading_dict(x) for x in reversed(rows)]

@app.get("/api/v1/stations/{station_id}/latest")
def latest(station_id:int):
    with SessionLocal() as db:
        station=db.get(Station,station_id)
        if not station:raise HTTPException(404,"Station not found")
        reading=db.scalar(select(TelemetryReading).where(TelemetryReading.station_id==station_id).order_by(desc(TelemetryReading.timestamp)))
        risk=db.scalar(select(RiskAssessment).where(RiskAssessment.station_id==station_id).order_by(desc(RiskAssessment.timestamp)))
        return {"station":station_dict(station),"reading":reading_dict(reading) if reading else None,"risk":risk_dict(risk) if risk else None}

@app.get("/api/v1/stations/{station_id}/risk")
def station_risk(station_id:int,limit:int=Query(100,ge=1,le=1000)):
    with SessionLocal() as db:return [risk_dict(x) for x in reversed(db.scalars(select(RiskAssessment).where(RiskAssessment.station_id==station_id).order_by(desc(RiskAssessment.timestamp)).limit(limit)).all())]

@app.get("/api/v1/stations/{station_id}/forecast")
def station_forecast(station_id:int):
    with SessionLocal() as db:
        row=db.scalar(select(Forecast).where(Forecast.station_id==station_id).order_by(desc(Forecast.created_at)))
        if not row:return {"available":False,"reason":"Insufficient declining water-level history"}
        return {"available":True,"id":row.id,"station_id":row.station_id,"forecast_for":iso(row.forecast_for),"predicted_value":row.predicted_value,"confidence":row.confidence,"metadata":row.forecast_metadata}

@app.get("/api/v1/alerts")
def alerts(resolved:bool|None=None):
    with SessionLocal() as db:
        q=select(Alert).order_by(desc(Alert.created_at))
        if resolved is not None:q=q.where(Alert.resolved==resolved)
        return [alert_dict(x) for x in db.scalars(q).all()]

@app.patch("/api/v1/alerts/{alert_id}/acknowledge")
async def acknowledge(alert_id:int):
    with SessionLocal() as db:
        item=db.get(Alert,alert_id)
        if not item:raise HTTPException(404,"Alert not found")
        item.acknowledged=True;db.commit();return alert_dict(item)

@app.patch("/api/v1/alerts/{alert_id}/resolve")
async def resolve(alert_id:int):
    with SessionLocal() as db:
        item=db.get(Alert,alert_id)
        if not item:raise HTTPException(404,"Alert not found")
        item.resolved=True;item.resolved_at=datetime.now(timezone.utc).replace(tzinfo=None);db.commit();out=alert_dict(item)
    await manager.broadcast("alert:resolved",out);return out

@app.get("/api/v1/dashboard/summary")
def dashboard_summary():
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

@app.get("/api/v1/dashboard/activity")
def activity(limit:int=20):
    with SessionLocal() as db:
        rows=db.scalars(select(RiskAssessment).order_by(desc(RiskAssessment.timestamp)).limit(limit)).all()
        stations={s.id:s for s in db.scalars(select(Station)).all()}
        return [{"id":r.id,"timestamp":iso(r.timestamp),"station_id":r.station_id,"station_code":stations[r.station_id].station_code,"station_name":stations[r.station_id].name,"risk_level":r.risk_level,"risk_score":r.overall_risk_score,"message":r.detected_factors[0] if r.detected_factors else "Telemetry stable"} for r in rows]

@app.post("/api/v1/simulator/start")
async def start_simulator():await simulator.start();return {"running":simulator.running,"interval_seconds":simulator.interval}
@app.post("/api/v1/simulator/stop")
async def stop_simulator():await simulator.stop();return {"running":simulator.running}
@app.get("/api/v1/simulator/status")
def simulator_status():return {"running":simulator.running,"interval_seconds":simulator.interval,"scenarios":simulator.scenarios}
@app.post("/api/v1/simulator/scenario")
def scenario(payload:dict):
    station_id=payload.get("station_id");scenario_name=payload.get("scenario","NORMAL")
    if not station_id:raise HTTPException(422,"station_id is required")
    with SessionLocal() as db:
        if not db.get(Station,int(station_id)):raise HTTPException(404,"Station not found")
    simulator.set_scenario(station_id,scenario_name,payload.get("intensity",1),payload.get("overrides"));return {"accepted":True,"station_id":station_id,"scenario":scenario_name.upper()}

@app.websocket("/ws/live")
async def live(ws:WebSocket):
    await manager.connect(ws)
    try:
        while True:await ws.receive_text()
    except WebSocketDisconnect:manager.disconnect(ws)
