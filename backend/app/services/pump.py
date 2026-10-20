from collections import defaultdict

LOW_THRESHOLD=20.0
HIGH_THRESHOLD=85.0
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

def predict_pump_schedule(events):
    """events: [{"triggered_at":datetime,"volume_liters":float|None}, ...] completed cycles only.
    Aggregates by (weekday, hour) to recommend when the next pump run is likely and how much it
    will need to move. Deterministic statistics over observed history, not a trained model."""
    timed=[e for e in events if e.get("volume_liters") is not None]
    if not timed: return None
    buckets=defaultdict(list)
    for e in timed: buckets[(e["triggered_at"].weekday(),e["triggered_at"].hour)].append(e["volume_liters"])
    (weekday,hour),volumes=sorted(buckets.items(),key=lambda kv:(-len(kv[1]),-sum(kv[1])))[0]
    daily=defaultdict(float)
    for e in timed: daily[e["triggered_at"].date()]+=e["volume_liters"]
    avg_daily=sum(daily.values())/len(daily)
    return {
        "predicted_weekday":DAYS[weekday],
        "predicted_hour":hour,
        "predicted_volume_liters":round(sum(volumes)/len(volumes),1),
        "avg_daily_volume_liters":round(avg_daily,1),
        "sample_size":len(timed),
        "confidence":round(min(95,40+len(timed)*3),1),
    }
