from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_analysis_request_reports_not_ready_before_startup() -> None:
    response = client.post(
        "/api/analyze/sample",
        json={
            "sample_id": "simulated_scenario",
            "bill": {"amount_inr": 4200, "units_kwh": 500},
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "not_ready",
            "message": "The analysis service is still starting",
            "details": None,
        }
    }


def test_invalid_bill_uses_canonical_error_code_and_status() -> None:
    response = client.post(
        "/api/analyze/sample",
        json={
            "sample_id": "simulated_scenario",
            "bill": {"amount_inr": 0, "units_kwh": 500},
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_bill"


def test_unknown_sample_uses_canonical_error_code_and_status() -> None:
    response = client.post(
        "/api/analyze/sample",
        json={
            "sample_id": "not_a_sample",
            "bill": {"amount_inr": 100, "units_kwh": 10},
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_sample"


def test_missing_bill_is_invalid_bill() -> None:
    response = client.post("/api/analyze/sample", json={"sample_id": "simulated_scenario"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_bill"


def test_openapi_describes_the_frozen_analysis_response() -> None:
    schema = client.get("/openapi.json").json()
    success_response = schema["paths"]["/api/analyze/sample"]["post"]["responses"]["200"]

    assert success_response["content"]["application/json"]["schema"]["$ref"].endswith(
        "/AnalysisResponse"
    )
    assert "AnalysisResponse" in schema["components"]["schemas"]
