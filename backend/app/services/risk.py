import numpy as np
from sklearn.ensemble import IsolationForest

THRESHOLDS={"ph":{"ideal_min":6.5,"ideal_max":8.5},"turbidity_ntu":{"warning":5,"critical":10},"conductivity_us_cm":{"baseline":500,"critical":1000},"water_level_percent":{"warning":30,"critical":15}}
WEIGHTS={"turbidity":.25,"ph":.20,"conductivity":.15,"anomaly":.20,"rate":.10,"context":.10}
FEATURES=["ph","turbidity_ntu","temperature_c","conductivity_us_cm","tds_ppm","water_level_percent","flow_rate_l_min"]

def _clamp(v): return max(0.0,min(100.0,float(v)))
def _ph(v):
    if v is None:return 0
    if 6.5<=v<=8.5:return 0
    return _clamp(min(abs(v-6.5),abs(v-8.5))*55)
def _turb(v):
    if v is None or v<=3:return 0
    return _clamp((v-3)/9*100)
def _cond(v):
    if v is None or v<=500:return 0
    return _clamp((v-500)/500*100)
def _level(v):
    if v is None or v>=30:return 0
    return _clamp((30-v)/20*100)

def assess_risk(reading, history):
    ph,turb,cond,level=(_ph(reading.get("ph")),_turb(reading.get("turbidity_ntu")),_cond(reading.get("conductivity_us_cm")),_level(reading.get("water_level_percent")))
    rate=0; anomaly=0; factors=[]
    if history:
        prev=history[-1]
        deltas=[]
        for key,scale in (("ph",.5),("turbidity_ntu",3),("conductivity_us_cm",100),("water_level_percent",10)):
            if reading.get(key) is not None and prev.get(key) is not None: deltas.append(abs(reading[key]-prev[key])/scale*100)
        rate=_clamp(max(deltas, default=0))
    if len(history)>=10:
        rows=[[float(h.get(k) or 0) for k in FEATURES] for h in history[-100:]]
        current=[float(reading.get(k) or 0) for k in FEATURES]
        try:
            model=IsolationForest(contamination=.1,random_state=42).fit(rows)
            raw=-float(model.decision_function([current])[0])
            anomaly=_clamp(40+raw*300) if model.predict([current])[0]<0 else _clamp(raw*100)
        except ValueError: anomaly=0
    context=max(level, 25 if (reading.get("temperature_c") or 25)>35 else 0)
    # Rule escalation keeps severe multi-sensor events explainable and safe.
    score=turb*.25+ph*.20+cond*.15+anomaly*.20+rate*.10+context*.10
    severe=sum(x>=70 for x in (turb,ph,cond))
    if severe>=2: score=max(score,78)
    elif turb>=90: score=max(score,75)
    score=round(_clamp(score),1)
    if turb>20:factors.append(f"Turbidity is elevated at {reading.get('turbidity_ntu'):.1f} NTU")
    if ph>20:factors.append(f"pH {reading.get('ph'):.2f} is outside the configured prototype band")
    if cond>20:factors.append("Conductivity is above the configured baseline")
    if level>20:factors.append("Water level is approaching the critical reserve")
    if anomaly>40:factors.append("The combined reading is unusual against recent station history")
    if rate>40:factors.append("Measurements are changing rapidly")
    level_name="safe" if score<25 else "watch" if score<50 else "warning" if score<75 else "critical"
    explanation="No abnormal patterns detected; telemetry is within configured prototype ranges." if not factors else " ".join(factors)+". The combined signal requires operator review."
    action="Continue routine monitoring." if level_name=="safe" else "Increase monitoring frequency and inspect the source." if level_name in ("watch","warning") else "Flag the source for verification and conduct appropriate water-quality testing before normal use continues."
    return {"overall_risk_score":score,"risk_level":level_name,"ph_score":ph,"turbidity_score":turb,"conductivity_score":cond,"water_level_score":level,"anomaly_score":anomaly,"detected_factors":factors,"explanation":explanation,"recommended_action":action,"confidence":round(min(95,55+len(history)*2),1),"model_version":"hybrid-iforest-1.0"}
