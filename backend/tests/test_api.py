import os
os.environ["DATABASE_URL"] = "sqlite:///./test_watersense.db"
from fastapi.testclient import TestClient
from app.main import app


def test_health_and_telemetry_pipeline():
    with TestClient(app) as client:
        stations = client.get("/api/v1/stations").json()
        assert len(stations) >= 12
        code = stations[0]["station_code"]
        response = client.post("/api/v1/telemetry", json={
            "station_code": code,
            "metrics": {"ph": 7.12, "turbidity_ntu": 2.9, "water_level_percent": 72},
            "device": {"source": "simulator", "battery_percent": 91}
        })
        assert response.status_code == 200
        body = response.json()
        assert body["accepted"] is True
        assert body["reading_id"]
        latest = client.get(f"/api/v1/stations/{stations[0]['id']}/latest")
        assert latest.status_code == 200


def test_unknown_station_rejected():
    with TestClient(app) as client:
        response = client.post("/api/v1/telemetry", json={
            "station_code": "UNKNOWN", "metrics": {"ph": 7.0}, "device": {"source": "manual"}
        })
        assert response.status_code == 404


def teardown_module():
    try: os.remove("test_watersense.db")
    except OSError: pass
