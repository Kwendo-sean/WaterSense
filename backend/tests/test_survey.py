import os
os.environ["DATABASE_URL"] = "sqlite:///./test_watersense.db"
os.environ["SURVEY_ADMIN_KEY"] = "test-admin-key"
from fastapi.testclient import TestClient
from app.main import app

VALID = {
    "idempotency_key": "test-key-0001",
    "location": "Nairobi",
    "residence_type": "Apartment or flat",
    "water_source": "Piped water",
    "has_tank": "Yes",
    "has_pump": "Yes",
    "pump_control": "Manually switched on and off",
    "problems": ["Tank running empty unexpectedly"],
    "problem_frequency": "A few times a month",
    "auto_control_usefulness": "Very useful",
    "desired_features": ["Automatic pump switching", "Alerts when water is running low"],
    "purchase_intent": "Probably",
    "price_range": "KSh 10,000-19,999",
    "main_concern": "Price",
    "other_comments": "Would love app notifications.",
}


def test_submit_valid_response():
    with TestClient(app) as client:
        r = client.post("/api/v1/survey/responses", json=VALID)
        assert r.status_code == 201
        body = r.json()
        assert body["duplicate"] is False
        assert body["id"]


def test_duplicate_idempotency_key_is_not_double_counted():
    with TestClient(app) as client:
        payload = {**VALID, "idempotency_key": "test-key-dup"}
        first = client.post("/api/v1/survey/responses", json=payload)
        second = client.post("/api/v1/survey/responses", json=payload)
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] == second.json()["id"]
        assert second.json()["duplicate"] is True


def test_more_than_three_desired_features_rejected():
    with TestClient(app) as client:
        payload = {**VALID, "idempotency_key": "test-key-toomany", "desired_features": [
            "Automatic pump switching", "Tank-level monitoring on a phone",
            "Alerts when water is running low", "Monitoring multiple tanks",
        ]}
        r = client.post("/api/v1/survey/responses", json=payload)
        assert r.status_code == 422


def test_pump_control_required_when_has_pump_yes():
    with TestClient(app) as client:
        payload = {**VALID, "idempotency_key": "test-key-nopumpcontrol", "pump_control": None}
        r = client.post("/api/v1/survey/responses", json=payload)
        assert r.status_code == 422


def test_results_requires_admin_key():
    with TestClient(app) as client:
        unauthorized = client.get("/api/v1/survey/results")
        assert unauthorized.status_code == 401
        wrong_key = client.get("/api/v1/survey/results", headers={"X-Admin-Key": "wrong"})
        assert wrong_key.status_code == 401
        ok = client.get("/api/v1/survey/results", headers={"X-Admin-Key": "test-admin-key"})
        assert ok.status_code == 200
        body = ok.json()
        assert body["total_responses"] >= 1
        assert "methodology_note" in body


def test_export_requires_admin_key():
    with TestClient(app) as client:
        unauthorized = client.get("/api/v1/survey/export")
        assert unauthorized.status_code == 401
        ok = client.get("/api/v1/survey/export", headers={"X-Admin-Key": "test-admin-key"})
        assert ok.status_code == 200
        assert "text/csv" in ok.headers["content-type"]
        assert "idempotency_key" not in ok.text  # internal field must not leak into export
        assert "id,submitted_at,location" in ok.text


def teardown_module():
    try:
        os.remove("test_watersense.db")
    except OSError:
        pass
