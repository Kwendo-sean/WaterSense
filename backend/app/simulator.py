import asyncio,random,os
from datetime import datetime,timezone
from sqlalchemy import select
from .core import SessionLocal
from .models import Station

class Simulator:
    def __init__(self): self.running=False;self.interval=float(os.getenv("SIMULATOR_INTERVAL_SECONDS","3"));self.task=None;self.scenarios={};self.steps={};self.overrides={};self.ingest=None
    async def start(self):
        if not self.running:
            self.running=True;self.task=asyncio.create_task(self._loop())
    async def stop(self):
        self.running=False
        if self.task:self.task.cancel();self.task=None
    def set_scenario(self,station_id,scenario,intensity=1.0,overrides=None):
        self.scenarios[int(station_id)]=scenario.upper();self.steps[int(station_id)]=0
        if overrides:self.overrides[int(station_id)]=overrides
    async def _loop(self):
        while self.running:
            db=SessionLocal();stations=db.scalars(select(Station)).all();db.close()
            for st in stations:
                if st.station_code=="WS-PROTOTYPE-01":continue
                scenario=self.scenarios.get(st.id,"NORMAL");step=self.steps.get(st.id,0);self.steps[st.id]=step+1
                noise=lambda n:random.uniform(-n,n)
                m={"ph":7.1+noise(.08),"turbidity_ntu":2.4+noise(.3),"temperature_c":23+noise(.5),"conductivity_us_cm":415+noise(12),"tds_ppm":208+noise(5),"water_level_percent":70+noise(1),"flow_rate_l_min":4.7+noise(.3)}
                progress=min(1,step/5)
                if scenario=="CONTAMINATION_EVENT":m.update(ph=7.1-1.25*progress,turbidity_ntu=2.5+13*progress,conductivity_us_cm=415+310*progress)
                elif scenario=="TANK_DEPLETION":m["water_level_percent"]=max(8,70-step*2.2)
                elif scenario=="LEAK_EVENT":m.update(water_level_percent=max(5,70-step*3.5),flow_rate_l_min=13+noise(1))
                elif scenario=="SENSOR_FAILURE":m.update(ph=14 if step%3==0 else 7.1,turbidity_ntu=None if step%2 else 900)
                elif scenario=="HEAVY_RAIN":m.update(turbidity_ntu=3+7*progress,conductivity_us_cm=415+100*progress)
                elif scenario=="RECOVERY":m.update(ph=6+1.1*progress,turbidity_ntu=15-12.5*progress,conductivity_us_cm=700-285*progress)
                m.update(self.overrides.get(st.id,{}))
                if self.ingest: await self.ingest({"station_code":st.station_code,"timestamp":datetime.now(timezone.utc),"metrics":m,"device":{"source":"simulator","battery_percent":91}})
            await asyncio.sleep(self.interval)
simulator=Simulator()
