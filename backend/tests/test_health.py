from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_not_ready_until_samples_are_initialized() -> None:
    response = TestClient(app).get("/api/health")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["ready"] is False
    assert [sample["id"] for sample in payload["samples"]] == [
        "typical_period",
        "simulated_scenario",
    ]
    assert payload["alerts"] == {"enabled": False, "topic_configured": False}
    assert payload["upload_enabled"] is False
