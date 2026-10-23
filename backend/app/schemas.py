import re
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

# -------- Market research survey --------
Location=Literal["Nairobi","Another part of Kenya","Outside Kenya"]
ResidenceType=Literal["Standalone house","Apartment or flat","Bedsitter or single room","Shared residence","Other"]
WaterSource=Literal["Piped water","Water vendor","Borehole","Well or spring","Rainwater","A combination of sources","Other"]
YesNoUnsure=Literal["Yes","No","Not sure"]
PumpControl=Literal["Manually switched on and off","Automatically controlled by a float switch or similar device","Controlled through a smart or remote system","Another method","Not sure"]
Problem=Literal["Tank overflowing","Tank running empty unexpectedly","Pump running when it should not","Pump failure or breakdown","High electricity consumption from pumping","Difficulty knowing the tank's water level","Water supply interruptions","None of these","Other"]
Frequency=Literal["Daily","Several times a week","About once a week","A few times a month","Rarely","Never"]
Usefulness=Literal["Very useful","Somewhat useful","Neither useful nor useless","Slightly useful","Not useful","Not sure"]
Feature=Literal["Automatic pump switching","Tank-level monitoring on a phone","Alerts when water is running low","Alerts when the pump may have a problem","Predictions of when the tank may need refilling","Monitoring multiple tanks","Monitoring electricity or water usage","None of these","Other"]
PurchaseIntent=Literal["Definitely","Probably","Not sure","Probably not","Definitely not"]
PriceRange=Literal["Less than KSh 10,000","KSh 10,000-19,999","KSh 20,000-29,999","KSh 30,000-39,999","KSh 40,000 or more","I would not buy one","Not sure"]
Concern=Literal["Price","Reliability","Electricity consumption","Installation complexity","Repair and maintenance costs","Internet connectivity requirements","Privacy or data security","I do not need one","Other"]

class SurveyIn(BaseModel):
    idempotency_key: str=Field(..., min_length=8, max_length=100)
    location: Location
    residence_type: ResidenceType
    water_source: WaterSource
    has_tank: YesNoUnsure
    has_pump: YesNoUnsure
    pump_control: PumpControl|None=None
    problems: list[Problem]=Field(default_factory=list)
    problem_frequency: Frequency
    auto_control_usefulness: Usefulness
    desired_features: list[Feature]=Field(default_factory=list)
    purchase_intent: PurchaseIntent
    price_range: PriceRange
    main_concern: Concern
    other_comments: str|None=Field(None, max_length=500)

    @model_validator(mode="after")
    def validate_rules(self):
        if self.has_pump=="Yes" and not self.pump_control:
            raise ValueError("pump_control is required when has_pump is 'Yes'")
        if self.has_pump!="Yes" and self.pump_control:
            raise ValueError("pump_control must be empty when has_pump is not 'Yes'")
        if len(self.desired_features)>3:
            raise ValueError("desired_features allows at most 3 selections")
        if len(set(self.problems))!=len(self.problems):
            raise ValueError("problems contains duplicate selections")
        if len(set(self.desired_features))!=len(self.desired_features):
            raise ValueError("desired_features contains duplicate selections")
        if self.other_comments is not None:
            cleaned=re.sub(r"<[^>]+>","",self.other_comments)
            cleaned="".join(ch for ch in cleaned if ch.isprintable() or ch in "\n\t").strip()
            object.__setattr__(self,"other_comments",cleaned or None)
        return self
