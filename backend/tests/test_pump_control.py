import os
os.environ["DATABASE_URL"] = "sqlite:///./test_watersense.db"
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from app.main import app
from app.services import pump_control

ADMIN = {"X-Admin-Key": "test-admin-key"}
TZ = ZoneInfo("Africa/Nairobi")


def _station(client, code):
    r = client.post("/api/v1/stations", headers=ADMIN, json={
        "station_code": code, "name": code, "station_type": "tank",
        "latitude": -1.29, "longitude": 36.82, "location_text": "test bench",
    })
    assert r.status_code in (201, 409)
    return next(s for s in client.get("/api/v1/stations", headers=ADMIN).json() if s["station_code"] == code)


def _post(client, code, level, pump_on=False, run_ms=0, **extra):
    r = client.post("/api/v1/telemetry", json={
        "station_code": code, "metrics": {"water_level_percent": level},
        "device": {"source": "arduino", "pump_on": pump_on, "pump_run_ms": run_ms, **extra},
    })
    assert r.status_code == 200, r.text
    return r.json()


def _sched(start, minutes, repeat="daily", run_date=None, done_on=None):
    return SimpleNamespace(id=1, start_time=start, duration_minutes=minutes, repeat=repeat,
                           run_date=run_date, done_on=done_on, enabled=True)


def test_manual_mode_is_sent_to_the_device_and_full_tank_hands_back_to_auto():
    with TestClient(app) as client:
        st = _station(client, "WS-TEST-CTRL-1")
        code, sid = st["station_code"], st["id"]
        assert _post(client, code, 50)["pump_command"] == "A"

        r = client.put(f"/api/v1/stations/{sid}/pump/control", headers=ADMIN, json={"mode": "on"})
        assert r.status_code == 200 and r.json()["command"] == "1"
        assert _post(client, code, 51, True)["pump_command"] == "1"

        # The forced fill ends at a full tank and control returns to automatic.
        assert _post(client, code, 100, False)["pump_command"] == "A"
        assert client.get(f"/api/v1/stations/{sid}/pump/control", headers=ADMIN).json()["mode"] == "auto"

        client.put(f"/api/v1/stations/{sid}/pump/control", headers=ADMIN, json={"mode": "off"})
        assert _post(client, code, 10)["pump_command"] == "0"
        client.put(f"/api/v1/stations/{sid}/pump/control", headers=ADMIN, json={"mode": "auto"})


def test_schedule_endpoints_validate_and_run_now():
    with TestClient(app) as client:
        st = _station(client, "WS-TEST-CTRL-2")
        code, sid = st["station_code"], st["id"]
        assert client.post(f"/api/v1/stations/{sid}/pump/schedules", headers=ADMIN,
                           json={"start_time": "25:00", "duration_minutes": 5}).status_code == 422
        assert client.post(f"/api/v1/stations/{sid}/pump/schedules",
                           json={"start_time": "06:00", "duration_minutes": 5}).status_code == 401

        # A window that is already under way starts immediately.
        start = (datetime.now(TZ) - timedelta(minutes=1)).strftime("%H:%M")
        r = client.post(f"/api/v1/stations/{sid}/pump/schedules", headers=ADMIN,
                        json={"start_time": start, "duration_minutes": 10, "repeat": "once"})
        assert r.status_code == 201
        state = r.json()
        assert state["command"] == "S" and state["active_schedule"]
        assert _post(client, code, 40)["pump_command"] == "S"

        # Manual off overrides a running schedule.
        client.put(f"/api/v1/stations/{sid}/pump/control", headers=ADMIN, json={"mode": "off"})
        assert _post(client, code, 40)["pump_command"] == "0"
        client.put(f"/api/v1/stations/{sid}/pump/control", headers=ADMIN, json={"mode": "auto"})

        # Reaching full ends a one-off schedule for good.
        assert _post(client, code, 100)["pump_command"] == "A"
        assert client.get(f"/api/v1/stations/{sid}/pump/control", headers=ADMIN).json()["schedules"] == []


def test_schedule_delete():
    with TestClient(app) as client:
        st = _station(client, "WS-TEST-CTRL-3")
        sid = st["id"]
        state = client.post(f"/api/v1/stations/{sid}/pump/schedules", headers=ADMIN,
                            json={"start_time": "03:00", "duration_minutes": 15, "repeat": "daily"}).json()
        item = state["schedules"][-1]
        assert item["next_run"]
        r = client.delete(f"/api/v1/stations/{sid}/pump/schedules/{item['id']}", headers=ADMIN)
        assert r.status_code == 200 and all(s["id"] != item["id"] for s in r.json()["schedules"])
        assert client.delete(f"/api/v1/stations/{sid}/pump/schedules/{item['id']}", headers=ADMIN).status_code == 404


def test_daily_window_crosses_midnight_and_runs_once_per_day():
    s = _sched("23:50", 20)
    late = datetime(2026, 10, 25, 0, 5, tzinfo=TZ)
    assert pump_control.resolve(None, [s], 50, late)[0] == "S"
    # A full tank cuts the window short; it must not restart the same night.
    assert pump_control.resolve(None, [s], 100, late)[0] == "A"
    assert s.done_on == "2026-10-24"
    assert pump_control.resolve(None, [s], 60, late)[0] == "A"
    assert pump_control.next_run(s, late) == datetime(2026, 10, 25, 23, 50, tzinfo=TZ)


def test_one_off_schedule_expires_after_its_window():
    now = datetime(2026, 10, 25, 9, 0, tzinfo=TZ)
    assert pump_control.first_run_date("08:00", 30, now) == "2026-10-26"
    assert pump_control.first_run_date("08:45", 30, now) == "2026-10-25"
    s = _sched("08:00", 30, repeat="once", run_date="2026-10-25")
    command, active, changed = pump_control.resolve(None, [s], 50, now)
    assert command == "A" and active is None and changed and not s.enabled


def test_one_off_schedule_on_a_chosen_date_within_a_month():
    with TestClient(app) as client:
        sid = _station(client, "WS-TEST-CTRL-DATE")["id"]
        today = datetime.now(TZ).date()
        post = lambda body: client.post(f"/api/v1/stations/{sid}/pump/schedules", headers=ADMIN, json=body)

        r = post({"start_time": "07:30", "duration_minutes": 15, "repeat": "once", "run_date": (today + timedelta(days=20)).isoformat()})
        assert r.status_code == 201
        item = r.json()["schedules"][-1]
        assert item["run_date"] == (today + timedelta(days=20)).isoformat()
        assert item["next_run"].startswith(f"{(today + timedelta(days=20)).isoformat()}T07:30")

        too_far = post({"start_time": "07:30", "duration_minutes": 15, "repeat": "once", "run_date": (today + timedelta(days=32)).isoformat()})
        assert too_far.status_code == 422 and "31 days" in too_far.json()["detail"]
        past = post({"start_time": "07:30", "duration_minutes": 15, "repeat": "once", "run_date": (today - timedelta(days=1)).isoformat()})
        assert past.status_code == 422 and "passed" in past.json()["detail"]
        assert post({"start_time": "07:30", "duration_minutes": 15, "run_date": "2026-13-40"}).status_code == 422
