from app.services.risk import assess_risk


def test_safe_reading_scores_safe():
    result = assess_risk({"ph": 7.1, "turbidity_ntu": 2.0, "conductivity_us_cm": 410}, [])
    assert result["risk_level"] == "safe"
    assert result["overall_risk_score"] < 25


def test_contamination_progresses_to_critical():
    history = [{"ph": 7.1, "turbidity_ntu": 2.5, "conductivity_us_cm": 410}] * 12
    result = assess_risk({"ph": 5.8, "turbidity_ntu": 16.0, "conductivity_us_cm": 720}, history)
    assert result["risk_level"] == "critical"
    assert result["overall_risk_score"] >= 75
    assert "turbidity" in " ".join(result["detected_factors"]).lower()
    assert result["recommended_action"]
