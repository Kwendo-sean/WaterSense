from datetime import datetime,timedelta,timezone
import math,random
from sqlalchemy import select,func
from .core import SessionLocal
from .models import Station,TelemetryReading,RiskAssessment,Alert,Forecast,PumpEvent
from .services.risk import assess_risk
from .services.forecast import calculate_forecast
from .services.pump import LOW_THRESHOLD,HIGH_THRESHOLD

STATIONS=[
("WS-NBI-001","Karura Reservoir Demo","reservoir",-1.2358,36.8328,"Karura, Nairobi"),
("WS-NBI-002","Westlands Tank Demo","tank",-1.2676,36.8108,"Westlands, Nairobi"),
("WS-NBI-003","Mathare Borehole Demo","borehole",-1.2584,36.8572,"Mathare, Nairobi"),
("WS-NBI-004","Kibera Demo Node 04","community_point",-1.3133,36.7890,"Kibera, Nairobi"),
("WS-NBI-005","Langata School Demo","school",-1.3630,36.7430,"Langata, Nairobi"),
("WS-NBI-006","Embakasi Tank Demo","tank",-1.3190,36.8950,"Embakasi, Nairobi"),
("WS-NBI-007","Ruiru River Demo","river",-1.1460,36.9600,"Ruiru, Kiambu"),
("WS-NBI-008","Kasarani Tap Demo","tap",-1.2180,36.8970,"Kasarani, Nairobi"),
("WS-NBI-009","Dagoretti Borehole Demo","borehole",-1.2920,36.7370,"Dagoretti, Nairobi"),
("WS-NBI-010","Muthaiga Tank Demo","tank",-1.2480,36.8160,"Muthaiga, Nairobi"),
("WS-NBI-011","Ngong Community Demo","community_point",-1.3610,36.6560,"Ngong, Kajiado"),
("WS-NBI-012","Athi River Demo","river",-1.4560,36.9780,"Athi River, Machakos") ]

def seed_database():
    random.seed(42); db=SessionLocal()
    if db.scalar(select(func.count()).select_from(Station)):
        db.close();return
    now=datetime.now(timezone.utc).replace(tzinfo=None)
    for idx,(code,name,typ,lat,lng,loc) in enumerate(STATIONS):
        st=Station(station_code=code,name=name,station_type=typ,latitude=lat,longitude=lng,location_text=loc,source_type="simulator")
        db.add(st);db.flush(); history=[]
        for step in range(97):
            ts=now-timedelta(hours=48)+timedelta(minutes=30*step)
            phase=step/8+idx
            level=max(18,86-step*(.20 if typ=="tank" else .04)+math.sin(phase)*1.2)
            vals={"ph":7.1+math.sin(phase)*.12,"turbidity_ntu":2.2+abs(math.sin(phase*.8))*.8,"temperature_c":22+math.sin(phase*.4)*2,"conductivity_us_cm":405+math.sin(phase)*18,"tds_ppm":205+math.sin(phase)*8,"water_level_percent":level,"flow_rate_l_min":4.4+math.sin(phase)*.5}
            # Seed distinct current states while keeping most stations safe.
            if step>92 and idx==3: vals.update(ph=6.0,turbidity_ntu=14+(step-93)*.6,conductivity_us_cm=690)
            elif step>93 and idx==7: vals["turbidity_ntu"]=7.2
            elif step>94 and idx==5: vals["water_level_percent"]=24
            rd=TelemetryReading(station_id=st.id,timestamp=ts,source="simulator",battery_percent=91-idx,raw_payload={},**vals);db.add(rd);db.flush()
            # Seed history quickly; live ingestion enables baseline/Isolation Forest analysis.
            risk=assess_risk(vals,[]); history.append(vals)
            ra=RiskAssessment(station_id=st.id,reading_id=rd.id,timestamp=ts,**risk);db.add(ra)
            st.status=risk["risk_level"];st.last_seen_at=ts
        if typ=="tank":
            f=calculate_forecast([(now-timedelta(hours=6-i),86-i*6) for i in range(7)])
            if f:
                metadata={**f,"forecast_for":f["forecast_for"].isoformat()}
                db.add(Forecast(station_id=st.id,forecast_for=f["forecast_for"],predicted_value=15,confidence=f["confidence"],forecast_metadata=metadata))
            # Seed two refill cycles a day for the past two weeks so the pump-scheduling
            # prediction has a real pattern to aggregate on first load, not an empty state.
            for day in range(14,0,-1):
                for hour in (6,18):
                    trigger=now-timedelta(days=day,hours=-hour)+timedelta(minutes=random.uniform(-15,15))
                    trigger_level=LOW_THRESHOLD+random.uniform(-2,2)
                    stop_level=HIGH_THRESHOLD+random.uniform(-2,2)
                    volume=max(0.0,(stop_level-trigger_level)/100*st.pump_capacity_liters)
                    stopped=trigger+timedelta(minutes=random.uniform(25,50))
                    db.add(PumpEvent(station_id=st.id,triggered_at=trigger,trigger_level=trigger_level,stopped_at=stopped,stop_level=stop_level,volume_liters=volume))
            st.pump_status="off"
    db.flush()
    nodes=db.scalars(select(Station).order_by(Station.id)).all()
    for i in range(5):
        resolved=i<3; st=nodes[3 if i>=3 else i]
        db.add(Alert(station_id=st.id,severity="critical" if i==4 else "warning",type="water_quality",title="Turbidity pattern requires review",message="Demo telemetry moved outside the configured operating band.",recommended_action="Verify the source and conduct appropriate field testing.",acknowledged=resolved,resolved=resolved,resolved_at=now-timedelta(hours=i) if resolved else None))
    db.commit();db.close()
