"""The network is the two hardware prototypes: the Arduino tank-and-pump rig and
the ESP32 sensor rig.

  python -m app.seed --prune   deletes every other station and all of its data
                               (readings, risk, alerts, forecasts, pump history).
"""
import sys
from sqlalchemy import select, delete
from .core import SessionLocal
from .models import Station, TelemetryReading, RiskAssessment, Alert, Forecast, PumpEvent, PumpControl, PumpSchedule

PROTOTYPE_CODE="WS-PROTOTYPE-01"
PROTOTYPE=dict(station_code=PROTOTYPE_CODE,name="Breadboard Prototype",description="Arduino Uno tank level and pump controller",
               station_type="tank",latitude=-1.2864,longitude=36.8172,location_text="Nairobi, Kenya",source_type="arduino",
               pump_capacity_liters=5000.0)
# Sits a little away from the first so the two map pins don't overlap.
PROTOTYPE_2=dict(station_code="WS-PROTOTYPE-02",name="ESP32 Sensor Prototype",description="ESP32-S3 ultrasonic level and flow sensors",
                 station_type="tank",latitude=-1.2921,longitude=36.8219,location_text="Nairobi, Kenya",source_type="esp32",
                 pump_capacity_liters=20.0)
PROTOTYPES=(PROTOTYPE,PROTOTYPE_2)
PROTOTYPE_CODES=tuple(p["station_code"] for p in PROTOTYPES)

def seed_database():
    """Create any missing prototype. Existing rows are left alone."""
    with SessionLocal() as db:
        for p in PROTOTYPES:
            if not db.scalar(select(Station).where(Station.station_code==p["station_code"])):
                db.add(Station(**p))
        db.commit()

def prune_to_prototype():
    with SessionLocal() as db:
        ids=db.scalars(select(Station.id).where(Station.station_code.not_in(PROTOTYPE_CODES))).all()
        if ids:
            # Children first: RiskAssessment references readings, everything references stations.
            for model in (Alert,RiskAssessment,Forecast,PumpEvent,PumpControl,PumpSchedule,TelemetryReading):
                db.execute(delete(model).where(model.station_id.in_(ids)))
            db.execute(delete(Station).where(Station.id.in_(ids)))
        for p in PROTOTYPES:
            proto=db.scalar(select(Station).where(Station.station_code==p["station_code"]))
            if proto is None: db.add(Station(**p))
            else:
                for k in ("latitude","longitude","location_text","source_type"): setattr(proto,k,p[k])
        db.commit()
    return len(ids)

if __name__=="__main__":
    if "--prune" not in sys.argv: raise SystemExit(__doc__)
    print(f"removed {prune_to_prototype()} station(s); {', '.join(PROTOTYPE_CODES)} kept in Nairobi")
