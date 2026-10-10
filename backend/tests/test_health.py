from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_not_ready_before_startup_runs() -> None:
    # Without the `with` block TestClient does not run the lifespan, so nothing is loaded.
    response = TestClient(app).get("/api/health")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["ready"] is False
    assert payload["samples"] == []
    assert payload["alerts"] == {"enabled": False, "topic_configured": False}
    assert payload["upload_enabled"] is False
