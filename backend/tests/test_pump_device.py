import os
os.environ["DATABASE_URL"] = "sqlite:///./test_watersense.db"
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.services.tank_insights import analyze_tank

ADMIN = {"X-Admin-Key": "test-admin-key"}


def _station(client, code):
    r = client.post("/api/v1/stations", headers=ADMIN, json={
        "station_code": code, "name": code, "station_type": "tank",
        "latitude": -1.29, "longitude": 36.82, "location_text": "test bench",
    })
    assert r.status_code in (201, 409)
    return next(s for s in client.get("/api/v1/stations", headers=ADMIN).json() if s["station_code"] == code)


def _post(client, code, ts, level, pump_on, run_ms, **extra):
    r = client.post("/api/v1/telemetry", json={
        "station_code": code, "timestamp": ts.isoformat(),
        "metrics": {"water_level_percent": level},
        "device": {"source": "arduino", "pump_on": pump_on, "pump_run_ms": run_ms, **extra},
    })
    assert r.status_code == 200, r.text


def test_device_pump_state_is_mirrored_and_volume_metered_from_run_time():
    with TestClient(app) as client:
        st = _station(client, "WS-TEST-HW-1")
        t = datetime.now(timezone.utc) - timedelta(minutes=5)
        _post(client, st["station_code"], t, 15, True, 0)
        pump = client.get(f"/api/v1/stations/{st['id']}/pump", headers=ADMIN).json()
        assert pump["pump_status"] == "on"
        assert pump["current_cycle"]["volume_liters"] == 0

        # 60 s of motor time at the rated 20 L/min is 20 L, counted while running.
        _post(client, st["station_code"], t + timedelta(seconds=60), 40, True, 60000)
        pump = client.get(f"/api/v1/stations/{st['id']}/pump", headers=ADMIN).json()
        assert pump["current_cycle"]["volume_liters"] == 20
        assert pump["total_volume_liters"] == 20

        _post(client, st["station_code"], t + timedelta(seconds=90), 86, False, 90000)
        pump = client.get(f"/api/v1/stations/{st['id']}/pump", headers=ADMIN).json()
        assert pump["pump_status"] == "off"
        assert pump["current_cycle"] is None
        assert pump["total_cycles"] == 1
        assert pump["recent_events"][0]["volume_liters"] == 30
        assert pump["recent_events"][0]["stop_level"] == 86

        latest = client.get(f"/api/v1/stations/{st['id']}/latest", headers=ADMIN).json()
        assert latest["reading"]["pump_on"] is False
        assert latest["reading"]["pump_run_ms"] == 90000


def test_device_reboot_restarts_run_counter_without_losing_or_inventing_volume():
    with TestClient(app) as client:
        st = _station(client, "WS-TEST-HW-2")
        t = datetime.now(timezone.utc) - timedelta(minutes=5)
        _post(client, st["station_code"], t, 10, True, 50000)
        _post(client, st["station_code"], t + timedelta(seconds=10), 12, True, 3000)  # board rebooted
        pump = client.get(f"/api/v1/stations/{st['id']}/pump", headers=ADMIN).json()
        assert pump["current_cycle"]["volume_liters"] == 1  # 3 s at 20 L/min


def test_insights_endpoint_requires_key_and_describes_state():
    with TestClient(app) as client:
        st = _station(client, "WS-TEST-HW-3")
        assert client.get(f"/api/v1/stations/{st['id']}/insights").status_code == 401
        _post(client, st["station_code"], datetime.now(timezone.utc), 50, False, 0, water_contact=False)
        body = client.get(f"/api/v1/stations/{st['id']}/insights", headers=ADMIN).json()
        assert body["engine"] == "deterministic"
        assert body["headline"].startswith("Idle")
        assert body["metrics"]["liters_in_tank"] == 2500
        assert body["findings"]


def _readings(now, levels, pump_on, step_s=10, **extra):
    start = now - timedelta(seconds=step_s * (len(levels) - 1))
    return [{"timestamp": start + timedelta(seconds=i * step_s), "level": lv, "pump_on": pump_on,
             "water_contact": extra.get("water_contact", False), "motion": None} for i, lv in enumerate(levels)]


def test_dry_run_is_flagged_when_pump_runs_without_level_rising():
    now = datetime(2026, 10, 23, 12, 0, 0)
    out = analyze_tank(now=now, capacity_liters=5000, flow_lpm=20, pump_on_fallback=True,
                       readings=_readings(now, [12] * 13, True),
                       events=[{"triggered_at": now - timedelta(minutes=4), "stopped_at": None, "volume_liters": 80}])
    assert out["status"] == "attention"
    assert out["findings"][0]["title"] == "Pump running but the level is not rising"


def test_water_contact_is_critical():
    now = datetime(2026, 10, 23, 12, 0, 0)
    out = analyze_tank(now=now, capacity_liters=5000, flow_lpm=20, pump_on_fallback=False,
                       readings=_readings(now, [60] * 5, False, water_contact=True), events=[])
    assert out["status"] == "fault"
    assert out["findings"][0]["title"] == "Water detected at the tank base"


def test_normal_refill_reports_time_to_full():
    now = datetime(2026, 10, 23, 12, 0, 0)
    out = analyze_tank(now=now, capacity_liters=5000, flow_lpm=20, pump_on_fallback=True,
                       readings=_readings(now, [30, 32, 34, 36, 38, 40], True),
                       events=[{"triggered_at": now - timedelta(minutes=1), "stopped_at": None, "volume_liters": 20}])
    assert out["status"] == "normal"
    assert out["metrics"]["minutes_to_full"] == 112.5  # 45% of 5000 L at 20 L/min
    assert out["headline"].startswith("Refilling")


def teardown_module():
    try: os.remove("test_watersense.db")
    except OSError: pass
