"""Deterministic tank and pump analysis.

Rule-based on purpose: every finding can be traced to a measured value, which
is what we want to validate before handing the same inputs to an LLM.
"""
from datetime import timedelta
from .pump import LOW_THRESHOLD, HIGH_THRESHOLD

MODEL_VERSION="tank-rules-1.0"
RATE_WINDOW_S=120
MIN_RATE_SPAN_S=20
NOISE_PERCENT=1.5   # level sensors jitter about ±1%; smaller net changes count as steady
OFFLINE_AFTER_S=30
DRY_RUN_AFTER_MIN=2.0
SEVERITY_ORDER={"critical":0,"warning":1,"info":2}

def _slope_per_min(points):
    """Least-squares slope of level (%) against time (minutes)."""
    if len(points)<3: return None
    t0=points[0][0]
    xs=[(t-t0).total_seconds()/60 for t,_ in points]; ys=[v for _,v in points]
    mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
    den=sum((x-mx)**2 for x in xs)
    if den<1e-9: return None
    return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/den

def _level_rate(points):
    """%/min, 0.0 when the change is within sensor noise, None until there's enough history."""
    if len(points)<3 or (points[-1][0]-points[0][0]).total_seconds()<MIN_RATE_SPAN_S: return None
    slope=_slope_per_min(points)
    if slope is None: return None
    span_min=(points[-1][0]-points[0][0]).total_seconds()/60
    return 0.0 if abs(slope*span_min)<NOISE_PERCENT else slope

def _duty_cycle(readings,since):
    window=[r for r in readings if r["timestamp"]>=since and r["pump_on"] is not None]
    if len(window)<2: return None
    on=total=0.0
    for a,b in zip(window,window[1:]):
        dt=(b["timestamp"]-a["timestamp"]).total_seconds()
        total+=dt
        if a["pump_on"]: on+=dt
    return round(on/total*100,1) if total>0 else None

def _fmt_minutes(m):
    if m is None: return None
    if m<1: return "under a minute"
    if m<90: return f"{m:.0f} min"
    return f"{m/60:.1f} h"

def analyze_tank(*,now,capacity_liters,flow_lpm,readings,events,pump_on_fallback):
    """readings: ascending dicts {timestamp, level, pump_on, water_contact, motion}.
    events: pump cycles (newest first) as dicts {triggered_at, stopped_at, volume_liters}."""
    base={"engine":"deterministic","model_version":MODEL_VERSION,"generated_at":now}
    levels=[r for r in readings if r["level"] is not None]
    if not levels:
        return {**base,"status":"no_data","headline":"Waiting for the first water-level reading","summary":"No level readings have arrived from this station yet.","findings":[],"recommended_action":"Check the device is powered and the bridge is running.","metrics":{},"confidence":0.0}

    last=levels[-1]; level=last["level"]
    pump_on=last["pump_on"] if last["pump_on"] is not None else pump_on_fallback
    liters=level/100*capacity_liters
    last_seen=(now-last["timestamp"]).total_seconds()
    recent=[(r["timestamp"],r["level"]) for r in levels if r["timestamp"]>=last["timestamp"]-timedelta(seconds=RATE_WINDOW_S)]
    rate=_level_rate(recent)

    open_cycle=next((e for e in events if e["stopped_at"] is None),None)
    cycle_minutes=(now-open_cycle["triggered_at"]).total_seconds()/60 if open_cycle else None
    cycle_liters=(open_cycle["volume_liters"] or 0.0) if open_cycle else None
    day_ago=now-timedelta(hours=24)
    day_events=[e for e in events if e["triggered_at"]>=day_ago or e["stopped_at"] is None]
    pumped_24h=sum(e["volume_liters"] or 0.0 for e in day_events)
    completed_24h=[e for e in day_events if e["stopped_at"] is not None]
    starts_1h=sum(1 for e in events if e["triggered_at"]>=now-timedelta(hours=1))
    duty=_duty_cycle(readings,now-timedelta(hours=1))

    minutes_to_full=(max(0.0,HIGH_THRESHOLD-level)/100*capacity_liters/flow_lpm) if pump_on else None
    minutes_to_start=((level-LOW_THRESHOLD)/-rate) if (not pump_on and rate is not None and rate<-0.05 and level>LOW_THRESHOLD) else None

    findings=[]
    def add(severity,title,detail):findings.append({"severity":severity,"title":title,"detail":detail})

    if last_seen>OFFLINE_AFTER_S:
        add("critical","Device offline",f"No reading for {last_seen:.0f} s. Everything below describes the last known state.")
    if last.get("water_contact"):
        add("critical","Water detected at the tank base","The contact sensor is wet. That usually points to a leak, an overflow or a dripping fitting near the tank or pump.")
    if not pump_on and level<=LOW_THRESHOLD:
        add("critical","Tank is low but the pump is off",f"Level is {level:.0f}%, at or below the {LOW_THRESHOLD:.0f}% start point, yet the pump is not running. Check the controller and the pump's power supply.")
    if pump_on and level>=HIGH_THRESHOLD+5:
        add("critical","Pump still running above the full mark",f"Level is {level:.0f}% with the pump on; it should have stopped at {HIGH_THRESHOLD:.0f}%. Overflow risk. Check the stop control.")
    if pump_on and cycle_minutes is not None and cycle_minutes>=DRY_RUN_AFTER_MIN and rate is not None and rate<=0.2:
        add("warning","Pump running but the level is not rising",f"The pump has run for {_fmt_minutes(cycle_minutes)} while the level changed {rate:+.1f}%/min. Possible dry run, closed inlet valve, airlock or blocked suction. Running dry damages pumps.")
    if not pump_on and rate is not None and rate<=-3:
        add("warning","Level falling fast",f"The tank is draining at {-rate:.1f}%/min (about {-rate/100*capacity_liters:.0f} L/min) with the pump off. That is heavy draw-off or a leak.")
    if starts_1h>=4:
        add("warning","Pump short-cycling",f"The pump started {starts_1h} times in the last hour. Frequent starts wear the motor and usually mean the start and stop points are too close or there is a leak.")
    if level<=10:
        add("warning","Tank nearly empty",f"Only about {liters:.0f} L left ({level:.0f}%). Supply could run out before the refill catches up.")
    if not findings:
        add("info","Operating normally","Level, pump state and sensors are consistent with normal automatic operation.")
    findings.sort(key=lambda f:SEVERITY_ORDER[f["severity"]])

    if pump_on:
        trend=f"rising {rate:.1f}%/min" if rate is not None and rate>0.2 else "not yet rising" if rate is not None else "trend still building"
        headline=f"Refilling: tank at {level:.0f}%, {trend}"
    elif rate is not None and rate<-0.2:
        headline=f"Idle: tank at {level:.0f}%, draining {-rate:.1f}%/min"
    elif rate is not None and rate>0.2:
        headline=f"Idle: tank at {level:.0f}%, rising {rate:.1f}%/min from another inflow"
    else:
        headline=f"Idle: tank at {level:.0f}%, holding steady"

    parts=[f"The tank holds about {liters:,.0f} L of {capacity_liters:,.0f} L ({level:.0f}%)."]
    if pump_on:
        parts.append(f"The pump is running and has delivered {cycle_liters:,.1f} L in this cycle" + (f" over {_fmt_minutes(cycle_minutes)}." if cycle_minutes is not None else "."))
        parts.append(f"At the rated {flow_lpm:.0f} L/min it needs about {_fmt_minutes(minutes_to_full)} to reach the {HIGH_THRESHOLD:.0f}% stop point.")
    else:
        parts.append(f"The pump is off. It will start automatically at {LOW_THRESHOLD:.0f}%" + (f", roughly {_fmt_minutes(minutes_to_start)} from now at the current draw." if minutes_to_start is not None else "."))
    parts.append(f"In the last 24 h the pump moved {pumped_24h:,.1f} L over {len(completed_24h)} completed cycle{'s' if len(completed_24h)!=1 else ''}.")
    if duty is not None: parts.append(f"It ran {duty:.0f}% of the last hour.")

    top=findings[0]["severity"]
    status="offline" if last_seen>OFFLINE_AFTER_S else "fault" if top=="critical" else "attention" if top=="warning" else "normal"
    action={
        "critical":"Inspect the tank and pump now and confirm the controller and power before relying on automatic control.",
        "warning":"Check the pump inlet, valves and pipework at the next opportunity and keep watching the level trend.",
        "info":"No action needed. Automatic control is handling the tank.",
    }[top]
    confidence=round(min(95.0,45+len(recent)*1.5+len(completed_24h)*4),1)
    return {**base,"status":status,"headline":headline,"summary":" ".join(parts),"findings":findings,"recommended_action":action,
        "metrics":{"level_percent":round(level,1),"liters_in_tank":round(liters,1),"pump_on":pump_on,"level_rate_per_min":None if rate is None else round(rate,2),
            "minutes_to_full":None if minutes_to_full is None else round(minutes_to_full,1),"minutes_to_pump_start":None if minutes_to_start is None else round(minutes_to_start,1),
            "current_cycle_minutes":None if cycle_minutes is None else round(cycle_minutes,1),"current_cycle_liters":None if cycle_liters is None else round(cycle_liters,2),
            "pumped_24h_liters":round(pumped_24h,2),"cycles_24h":len(completed_24h),"pump_starts_1h":starts_1h,"duty_cycle_percent_1h":duty,"last_seen_seconds":round(last_seen,1),
            "water_contact":last.get("water_contact"),"motion":last.get("motion")},
        "confidence":confidence}
