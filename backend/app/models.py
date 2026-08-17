from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, Boolean, ForeignKey, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .core import Base

def now(): return datetime.now(timezone.utc)

class Station(Base):
    __tablename__="stations"
    id: Mapped[int]=mapped_column(primary_key=True)
    station_code: Mapped[str]=mapped_column(String, unique=True, index=True)
    name: Mapped[str]=mapped_column(String)
    description: Mapped[str]=mapped_column(String, default="Demo monitoring station")
    station_type: Mapped[str]=mapped_column(String, default="community_point")
    latitude: Mapped[float]=mapped_column(Float)
    longitude: Mapped[float]=mapped_column(Float)
    location_text: Mapped[str]=mapped_column(String)
    status: Mapped[str]=mapped_column(String, default="safe")
    installed_at: Mapped[datetime]=mapped_column(DateTime, default=now)
    last_seen_at: Mapped[datetime|None]=mapped_column(DateTime, nullable=True)
    source_type: Mapped[str]=mapped_column(String, default="simulator")
    created_at: Mapped[datetime]=mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime]=mapped_column(DateTime, default=now, onupdate=now)

class TelemetryReading(Base):
    __tablename__="telemetry_readings"
    id: Mapped[int]=mapped_column(primary_key=True)
    station_id: Mapped[int]=mapped_column(ForeignKey("stations.id"), index=True)
    timestamp: Mapped[datetime]=mapped_column(DateTime, default=now, index=True)
    ph: Mapped[float|None]=mapped_column(Float, nullable=True)
    turbidity_ntu: Mapped[float|None]=mapped_column(Float, nullable=True)
    temperature_c: Mapped[float|None]=mapped_column(Float, nullable=True)
    conductivity_us_cm: Mapped[float|None]=mapped_column(Float, nullable=True)
    tds_ppm: Mapped[float|None]=mapped_column(Float, nullable=True)
    water_level_percent: Mapped[float|None]=mapped_column(Float, nullable=True)
    flow_rate_l_min: Mapped[float|None]=mapped_column(Float, nullable=True)
    battery_percent: Mapped[float|None]=mapped_column(Float, nullable=True)
    signal_strength: Mapped[float|None]=mapped_column(Float, nullable=True)
    source: Mapped[str]=mapped_column(String, default="simulator")
    raw_payload: Mapped[dict]=mapped_column(JSON, default=dict)

class RiskAssessment(Base):
    __tablename__="risk_assessments"
    id: Mapped[int]=mapped_column(primary_key=True)
    station_id: Mapped[int]=mapped_column(ForeignKey("stations.id"), index=True)
    reading_id: Mapped[int]=mapped_column(ForeignKey("telemetry_readings.id"))
    timestamp: Mapped[datetime]=mapped_column(DateTime, default=now)
    overall_risk_score: Mapped[float]=mapped_column(Float)
    risk_level: Mapped[str]=mapped_column(String)
    ph_score: Mapped[float]=mapped_column(Float, default=0)
    turbidity_score: Mapped[float]=mapped_column(Float, default=0)
    conductivity_score: Mapped[float]=mapped_column(Float, default=0)
    water_level_score: Mapped[float]=mapped_column(Float, default=0)
    anomaly_score: Mapped[float]=mapped_column(Float, default=0)
    detected_factors: Mapped[list]=mapped_column(JSON, default=list)
    explanation: Mapped[str]=mapped_column(String)
    recommended_action: Mapped[str]=mapped_column(String)
    confidence: Mapped[float]=mapped_column(Float)
    model_version: Mapped[str]=mapped_column(String, default="hybrid-iforest-1.0")

class Alert(Base):
    __tablename__="alerts"
    id: Mapped[int]=mapped_column(primary_key=True)
    station_id: Mapped[int]=mapped_column(ForeignKey("stations.id"), index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime]=mapped_column(DateTime, default=now, onupdate=now)
    resolved_at: Mapped[datetime|None]=mapped_column(DateTime, nullable=True)
    severity: Mapped[str]=mapped_column(String)
    type: Mapped[str]=mapped_column(String, default="water_quality")
    title: Mapped[str]=mapped_column(String)
    message: Mapped[str]=mapped_column(String)
    recommended_action: Mapped[str]=mapped_column(String)
    acknowledged: Mapped[bool]=mapped_column(Boolean, default=False)
    resolved: Mapped[bool]=mapped_column(Boolean, default=False)

class Forecast(Base):
    __tablename__="forecasts"
    id: Mapped[int]=mapped_column(primary_key=True)
    station_id: Mapped[int]=mapped_column(ForeignKey("stations.id"), index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime, default=now)
    forecast_type: Mapped[str]=mapped_column(String, default="water_depletion")
    forecast_for: Mapped[datetime]=mapped_column(DateTime)
    predicted_value: Mapped[float]=mapped_column(Float)
    confidence: Mapped[float]=mapped_column(Float)
    forecast_metadata: Mapped[dict]=mapped_column("metadata", JSON, default=dict)
