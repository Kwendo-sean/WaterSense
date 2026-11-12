import os
os.environ["DATABASE_URL"] = "sqlite:///./test_watersense.db"
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.core import SessionLocal
from app.models import Station, PumpEvent
from app.seed import prune_to_prototype, PROTOTYPE_CODES
from app.services.pump import predict_pump_schedule, daily_pump_stats

ADMIN = {"X-Admin-Key": "test-admin-key"}


def _utc(y, m, d, h, mi=0):
    # Naive UTC, as stored. Nairobi is UTC+3.
    return datetime(y, m, d, h, mi)


def test_prediction_uses_hour_of_day_and_projects_next_run():
    # Starts at 07:xx Nairobi (04:xx UTC) on three days, plus one busy test hour on one day.
    events = [{"triggered_at": _utc(2026, 10, d, 4, 10), "volume_liters": 400} for d in (21, 22, 23)]
    events += [{"triggered_at": _utc(2026, 10, 23, 12, m), "volume_liters": 50} for m in range(0, 50, 10)]
    p = predict_pump_schedule(events, _utc(2026, 10, 25, 6, 0))  # 09:00 Nairobi: 07:00 has passed
    assert p["predicted_hour"] == 7
    assert p["next_run_at"].startswith("2026-10-26T07:00")
    assert p["days_at_hour"] == 3 and p["days_observed"] == 3
    assert p["predicted_volume_liters"] == 400


def test_daily_stats_group_by_local_day_and_include_today():
    now = _utc(2026, 10, 25, 6, 0)
    events = [
        {"triggered_at": _utc(2026, 10, 24, 22, 0), "volume_liters": 100},  # 01:00 on the 25th in Nairobi
        {"triggered_at": _utc(2026, 10, 24, 10, 0), "volume_liters": 40},
        {"triggered_at": _utc(2026, 10, 25, 5, 0), "volume_liters": None},  # running, nothing metered yet
    ]
    days = daily_pump_stats(events, now)
    assert len(days) == 7 and days[-1]["date"] == "2026-10-25"
    assert days[-1] == {"date": "2026-10-25", "volume_liters": 100.0, "cycles": 2}
    assert days[-2] == {"date": "2026-10-24", "volume_liters": 40.0, "cycles": 1}


def test_series_buckets_level_and_pump_share():
    with TestClient(app) as client:
        r = client.post("/api/v1/stations", headers=ADMIN, json={
            "station_code": "WS-TEST-SERIES", "name": "s", "station_type": "tank",
            "latitude": -1.29, "longitude": 36.82, "location_text": "bench"})
        assert r.status_code in (201, 409)
        sid = next(s["id"] for s in client.get("/api/v1/stations", headers=ADMIN).json() if s["station_code"] == "WS-TEST-SERIES")
        t0 = datetime.now(timezone.utc) - timedelta(minutes=30)
        for i, (lvl, on, ms) in enumerate([(20, True, 0), (40, True, 60000), (60, False, 120000)]):
            client.post("/api/v1/telemetry", json={"station_code": "WS-TEST-SERIES", "timestamp": (t0 + timedelta(minutes=i)).isoformat(),
                        "metrics": {"water_level_percent": lvl}, "device": {"source": "arduino", "pump_on": on, "pump_run_ms": ms}})
        body = client.get(f"/api/v1/stations/{sid}/series?minutes=60", headers=ADMIN).json()
        assert body["bucket_seconds"] == 15
        levels = [p["level"] for p in body["points"]]
        assert levels == [20, 40, 60]
        # The pump ran from the first reading to the last, so the bucket between is fully on.
        assert body["points"][1]["pump"] == 1 and 0 < body["points"][0]["pump"] <= 1
        assert client.get(f"/api/v1/stations/{sid}/series?minutes=60").status_code == 401

        pump = client.get(f"/api/v1/stations/{sid}/pump", headers=ADMIN).json()
        assert len(pump["daily"]) == 7 and pump["today"] == pump["daily"][-1]


def test_esp32_rig_reports_sensors_without_a_pump():
    with TestClient(app) as client:
        sid = next(s["id"] for s in client.get("/api/v1/stations", headers=ADMIN).json() if s["station_code"] == "WS-PROTOTYPE-02")
        # 10% would start a pump on any other station.
        r = client.post("/api/v1/telemetry", json={"station_code": "WS-PROTOTYPE-02", "metrics": {"water_level_percent": 10, "flow_rate_l_min": 2.5},
                        "device": {"source": "esp32", "distance_cm": 92.5, "flow_total_liters": 1.25}})
        assert r.status_code == 200
        latest = client.get(f"/api/v1/stations/{sid}/latest", headers=ADMIN).json()
        assert latest["reading"]["source"] == "esp32" and latest["reading"]["distance_cm"] == 92.5
        assert latest["reading"]["flow_total_liters"] == 1.25 and latest["station"]["pump_status"] == "off"
        ai = client.get(f"/api/v1/stations/{sid}/insights", headers=ADMIN).json()
        assert "Tank is low but the pump is off" not in [f["title"] for f in ai["findings"]]
        assert "No pump is wired" in ai["summary"]
    with SessionLocal() as db:
        assert db.scalar(select(PumpEvent).where(PumpEvent.station_id == sid)) is None


def test_prune_keeps_only_the_prototype_in_nairobi():
    with TestClient(app) as client:
        client.post("/api/v1/stations", headers=ADMIN, json={
            "station_code": "WS-TEST-PRUNE", "name": "p", "station_type": "tank",
            "latitude": 0, "longitude": 0, "location_text": "elsewhere"})
        client.post("/api/v1/telemetry", json={"station_code": "WS-TEST-PRUNE", "metrics": {"water_level_percent": 10},
                    "device": {"source": "arduino", "pump_on": True, "pump_run_ms": 0}})
    assert prune_to_prototype() >= 1
    with SessionLocal() as db:
        stations = db.scalars(select(Station)).all()
        assert sorted(s.station_code for s in stations) == sorted(PROTOTYPE_CODES)
        assert {s.location_text for s in stations} == {"Nairobi, Kenya"}
        assert db.scalar(select(PumpEvent).where(PumpEvent.station_id.not_in([s.id for s in stations]))) is None


def test_ai_findings_are_kept_as_episodes_with_evidence():
    import app.main as main
    from app.services.finding_history import record_findings
    from app.models import AiFinding
    with TestClient(app) as client:
        sid = next(s["id"] for s in client.get("/api/v1/stations", headers=ADMIN).json() if s["station_code"] == "WS-PROTOTYPE-02")
        main._findings_checked.pop(sid, None)
        client.post("/api/v1/telemetry", json={"station_code": "WS-PROTOTYPE-02", "metrics": {"water_level_percent": 50},
                    "device": {"source": "esp32", "pump_on": False, "pump_run_ms": 0, "water_contact": True}})
        hist = client.get(f"/api/v1/stations/{sid}/insights/history", headers=ADMIN).json()
        leak = next(i for i in hist["items"] if i["title"] == "Water detected at the tank base")
        assert leak["active"] and leak["severity"] == "critical" and leak["context"]["level_percent"] == 50
        assert "Operating normally" not in [i["title"] for i in hist["items"]]
        assert any(t["title"] == leak["title"] and t["episodes"] >= 1 for t in hist["by_title"])
        assert client.get(f"/api/v1/stations/{sid}/insights/history").status_code == 401

    with SessionLocal() as db:
        row = db.get(AiFinding, leak["id"])
        start = row.last_seen
        # Still present a moment later: same episode, one more confirmation.
        record_findings(db, sid, {"findings": [{"severity": "critical", "title": leak["title"], "detail": "still wet"}]}, start + timedelta(seconds=10))
        db.commit(); db.refresh(row)
        assert row.checks == 2 and row.last_detail == "still wet" and row.resolved_at is None
        # Gone, but within the grace period: stays open.
        record_findings(db, sid, {"findings": []}, start + timedelta(seconds=30))
        db.commit(); db.refresh(row)
        assert row.resolved_at is None
        # Gone past the grace period: closed at the last time it was confirmed.
        record_findings(db, sid, {"findings": []}, start + timedelta(seconds=200))
        db.commit(); db.refresh(row)
        assert row.resolved_at == start + timedelta(seconds=10)
