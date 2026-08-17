from datetime import timedelta
import numpy as np

def calculate_forecast(rows, critical_level=15):
    valid=[(t,float(v)) for t,v in rows if v is not None]
    if len(valid)<5:return None
    start=valid[0][0]
    x=np.array([(t-start).total_seconds()/3600 for t,_ in valid]); y=np.array([v for _,v in valid])
    if x[-1]-x[0] <= 0:return None
    slope,intercept=np.polyfit(x,y,1)
    if slope>=-.05 or y[-1]<=critical_level:return None
    target_x=(critical_level-intercept)/slope
    hours=float(max(0,target_x-x[-1]))
    predicted=slope*x+intercept
    ss_res=float(np.sum((y-predicted)**2)); ss_tot=float(np.sum((y-y.mean())**2))
    r2=max(0,1-ss_res/ss_tot) if ss_tot else 0
    return {"hours_to_critical":round(hours,2),"confidence":round(50+45*r2,1),"critical_level":critical_level,"slope_per_hour":round(float(slope),3),"forecast_for":valid[-1][0]+timedelta(hours=hours)}
