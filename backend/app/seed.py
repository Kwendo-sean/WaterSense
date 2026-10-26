"""The network is a single station: the Arduino tank-and-pump prototype.

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

def seed_database():
    """Create the prototype on a fresh database. Existing rows are left alone."""
    with SessionLocal() as db:
        if not db.scalar(select(Station).where(Station.station_code==PROTOTYPE_CODE)):
            db.add(Station(**PROTOTYPE));db.commit()

def prune_to_prototype():
    with SessionLocal() as db:
        ids=db.scalars(select(Station.id).where(Station.station_code!=PROTOTYPE_CODE)).all()
        if ids:
            # Children first: RiskAssessment references readings, everything references stations.
            for model in (Alert,RiskAssessment,Forecast,PumpEvent,PumpControl,PumpSchedule,TelemetryReading):
                db.execute(delete(model).where(model.station_id.in_(ids)))
            db.execute(delete(Station).where(Station.id.in_(ids)))
        proto=db.scalar(select(Station).where(Station.station_code==PROTOTYPE_CODE))
        if proto is None: db.add(Station(**PROTOTYPE))
        else:
            for k in ("latitude","longitude","location_text","source_type"): setattr(proto,k,PROTOTYPE[k])
        db.commit()
    return len(ids)

if __name__=="__main__":
    if "--prune" not in sys.argv: raise SystemExit(__doc__)
    print(f"removed {prune_to_prototype()} station(s); {PROTOTYPE_CODE} kept in Nairobi")
