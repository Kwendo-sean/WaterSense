from datetime import datetime, timedelta, timezone
from app.services.forecast import calculate_forecast


def test_declining_level_returns_time_to_critical():
    now = datetime.now(timezone.utc)
    rows = [(now + timedelta(hours=i), 60 - i * 5) for i in range(7)]
    forecast = calculate_forecast(rows, critical_level=15)
    assert forecast is not None
    assert 2.5 < forecast["hours_to_critical"] < 3.5
    assert forecast["confidence"] > 50


def test_flat_level_has_no_forecast():
    now = datetime.now(timezone.utc)
    rows = [(now + timedelta(hours=i), 60) for i in range(7)]
    assert calculate_forecast(rows) is None
