from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class Metrics(BaseModel):
    ph: float|None=Field(None, ge=0, le=14)
    turbidity_ntu: float|None=Field(None, ge=0, le=1000)
    temperature_c: float|None=Field(None, ge=-10, le=100)
    conductivity_us_cm: float|None=Field(None, ge=0, le=100000)
    tds_ppm: float|None=Field(None, ge=0, le=50000)
    water_level_percent: float|None=Field(None, ge=0, le=100)
    flow_rate_l_min: float|None=Field(None, ge=0, le=100000)
    @model_validator(mode="after")
    def at_least_one(self):
        if all(v is None for v in self.model_dump().values()): raise ValueError("at least one measurement is required")
        return self
class Device(BaseModel):
    source: Literal["simulator","arduino","esp32","manual","external"]="simulator"
    battery_percent: float|None=Field(None, ge=0, le=100)
    signal_strength: float|None=Field(None, ge=-150, le=0)
class TelemetryIn(BaseModel):
    station_code: str
    timestamp: datetime|None=None
    metrics: Metrics
    device: Device=Device()
class StationIn(BaseModel):
    station_code: str
    name: str
    description: str="Demo monitoring station"
    station_type: str="community_point"
    latitude: float
    longitude: float
    location_text: str
    source_type: str="simulator"
class StationPatch(BaseModel):
    name: str|None=None
    description: str|None=None
    status: str|None=None
    location_text: str|None=None
