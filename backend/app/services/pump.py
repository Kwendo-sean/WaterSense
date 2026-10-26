import os
from collections import defaultdict
from datetime import timezone, timedelta
from zoneinfo import ZoneInfo

LOW_THRESHOLD=20.0
HIGH_THRESHOLD=85.0
# Rated flow of a typical small domestic transfer pump. Hardware stations meter
# volume as motor run time x this rate, since the prototype has no flow meter.
PUMP_FLOW_LPM=20.0
DAYS=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

def evaluate_pump(pump_status,level,capacity_liters):
    """Deterministic motor control: low level starts the pump, high level stops it.
    Returns (new_status, action) where action is None, ("start",level), or ("stop",level,volume_liters)."""
    if level is None: return pump_status,None
    if pump_status=="off" and level<=LOW_THRESHOLD: return "on",("start",level)
    if pump_status=="on" and level>=HIGH_THRESHOLD:
        volume=max(0.0,(level-LOW_THRESHOLD)/100*capacity_liters)
        return "off",("stop",level,volume)
    return pump_status,None

def _local(dt):
    """Timestamps are stored as naive UTC; schedules should read in the site's local time."""
    try: tz=ZoneInfo(os.getenv("TZ") or "Africa/Nairobi")
    except Exception: return dt
    return dt.replace(tzinfo=timezone.utc).astimezone(tz)

def predict_pump_schedule(events, now=None):
    """events: [{"triggered_at":datetime,"volume_liters":float|None}, ...] completed cycles only.
    Finds the hour of the day the pump most often starts and projects its next occurrence
    (later today, else tomorrow). Deterministic statistics over observed history, not a
    trained model. Daily rather than weekly: a week-by-hour grid needs weeks of history
    before any one cell means anything."""
    # A cycle that moved no water carries no information about demand.
    timed=[e for e in events if (e.get("volume_liters") or 0)>0]
    if not timed: return None
    by_hour=defaultdict(list);days_by_hour=defaultdict(set);daily=defaultdict(lambda:[0.0,0])
    for e in timed:
        t=_local(e["triggered_at"])
        by_hour[t.hour].append(e["volume_liters"]);days_by_hour[t.hour].add(t.date())
        daily[t.date()][0]+=e["volume_liters"];daily[t.date()][1]+=1
    # Rank by how many different days the hour recurs on, so one busy test session
    # doesn't outweigh a habit seen every day.
    hour=max(by_hour,key=lambda h:(len(days_by_hour[h]),len(by_hour[h]),sum(by_hour[h])))
    volumes=by_hour[hour]
    local_now=_local(now) if now is not None else None
    next_run=None
    if local_now is not None:
        next_run=local_now.replace(hour=hour,minute=0,second=0,microsecond=0)
        if next_run<=local_now: next_run+=timedelta(days=1)
    recurring=len(days_by_hour[hour])
    return {
        "predicted_weekday":DAYS[(next_run or _local(timed[0]["triggered_at"])).weekday()],
        "predicted_hour":hour,
        "next_run_at":next_run.isoformat() if next_run else None,
        "predicted_volume_liters":round(sum(volumes)/len(volumes),1),
        "avg_daily_volume_liters":round(sum(v for v,_ in daily.values())/len(daily),1),
        "avg_daily_cycles":round(sum(n for _,n in daily.values())/len(daily),1),
        "days_observed":len(daily),
        "days_at_hour":recurring,
        "sample_size":len(timed),
        "confidence":round(min(95,30+recurring*12+min(len(volumes),10)),1),
    }

def daily_pump_stats(events, now, days=7):
    """Volume and cycle count per local calendar day, oldest first, ending today.
    events may include the running cycle; its volume so far counts toward today."""
    today=_local(now).date()
    out={today-timedelta(days=i):{"volume_liters":0.0,"cycles":0} for i in range(days-1,-1,-1)}
    for e in events:
        d=_local(e["triggered_at"]).date()
        if d in out:
            out[d]["volume_liters"]+=e.get("volume_liters") or 0.0
            out[d]["cycles"]+=1
    return [{"date":d.isoformat(),"volume_liters":round(v["volume_liters"],1),"cycles":v["cycles"]} for d,v in out.items()]
