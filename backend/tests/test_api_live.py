"""TS-A-01…05, TS-F-01…06 — the API with startup actually run against real artifacts."""

import json
import shutil
from pathlib import Path

import pytest
from conftest import ARTIFACTS
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas import AnalysisResponse

BILL = {"amount_inr": 4200, "units_kwh": 500}


def settings(tmp_path: Path, data_dir: Path, **env) -> Settings:
    frontend = tmp_path / "dist"
    frontend.mkdir(exist_ok=True)
    (frontend / "index.html").write_text("<!doctype html><title>AEA</title>", encoding="utf-8")
    base = {"AEA_DATA_DIR": str(data_dir), "AEA_FRONTEND_DIR": str(frontend)}
    base.update(env)
    return Settings.from_env(base)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(settings(tmp_path, ARTIFACTS))) as c:
        yield c


# ---- health / config / evaluation ---------------------------------------------------


def test_health_after_startup(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    h = r.json()
    assert h["ready"] is True
    assert h["status"] == "degraded"  # local mode: no S3 sync happened (honestly reported)
    assert h["s3_sync"]["state"] == "failed_using_cache"
    assert h["samples"] == [{"id": "simulated_scenario", "state": "ready", "detail": None}]
    states = {a["id"]: (a["registry_status"], a["runtime_state"]) for a in h["appliances"]}
    assert states["air_conditioner"] == ("candidate", "inactive")
    assert states["air_conditioner_sim"] == ("demo", "loaded")


def test_config_lists_only_available_samples_as_available(client):
    c = client.get("/api/config").json()
    available = {s["id"]: s["available"] for s in c["samples"]}
    assert available == {"typical_period": False, "simulated_scenario": True}
    assert c["evidence_level"] == "none" and c["alerts_enabled"] is False
    assert c["upload_enabled"] is False and c["emissions_available"] is False


def test_evaluation_is_served_unchanged(client):
    served = client.get("/api/evaluation").json()
    on_disk = json.loads((ARTIFACTS / "evaluation" / "evaluation.json").read_text(encoding="utf-8"))
    assert served == on_disk


# ---- analysis -----------------------------------------------------------------------


def test_analyze_simulated_scenario_returns_a_full_response(client):
    r = client.post("/api/analyze/sample", json={"sample_id": "simulated_scenario", "bill": BILL})
    assert r.status_code == 200
    body = AnalysisResponse.model_validate(r.json())
    assert body.source.simulated is True and body.summary.issues_count == 2
    assert body.alert.status == "disabled"  # alerts are off by default


def test_analysis_errors(client):
    bad_bill = client.post("/api/analyze/sample", json={"sample_id": "simulated_scenario", "bill": {"amount_inr": 0, "units_kwh": 5}})
    assert (bad_bill.status_code, bad_bill.json()["error"]["code"]) == (422, "invalid_bill")
    unknown = client.post("/api/analyze/sample", json={"sample_id": "nope", "bill": BILL})
    assert (unknown.status_code, unknown.json()["error"]["code"]) == (404, "unknown_sample")
    unavailable = client.post("/api/analyze/sample", json={"sample_id": "typical_period", "bill": BILL})
    assert (unavailable.status_code, unavailable.json()["error"]["code"]) == (503, "sample_unavailable")


def test_routing_api_404_is_json_and_spa_is_served(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    page = client.get("/")
    assert page.status_code == 200 and "AEA" in page.text
    assert "access-control-allow-origin" not in r.headers  # no CORS in production


def test_unexpected_error_is_internal_without_details(tmp_path, monkeypatch):
    import app.api.routes as routes

    def boom(*args, **kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(routes, "apply_bill", boom)
    with TestClient(create_app(settings(tmp_path, ARTIFACTS)), raise_server_exceptions=False) as c:
        r = c.post("/api/analyze/sample", json={"sample_id": "simulated_scenario", "bill": BILL})
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal"
    assert "secret" not in r.text


# ---- not ready / S3 sync --------------------------------------------------------------


def test_empty_data_dir_is_not_ready(tmp_path):
    with TestClient(create_app(settings(tmp_path, tmp_path / "empty"))) as c:
        assert c.get("/api/health").status_code == 503
        assert c.get("/api/health").json()["s3_sync"]["state"] == "failed_no_cache"
        assert c.get("/api/config").json()["error"]["code"] == "not_ready"
        r = c.post("/api/analyze/sample", json={"sample_id": "simulated_scenario", "bill": BILL})
        assert (r.status_code, r.json()["error"]["code"]) == (503, "not_ready")


class FakeS3:
    """Serves the repository's artifacts/ folder as if it were the bucket."""

    def __init__(self, source: Path, fail: bool = False):
        self.source, self.fail = source, fail

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        fake = self

        class Paginator:
            def paginate(self, Bucket):
                if fake.fail:
                    raise ConnectionError("network down")
                keys = [p.relative_to(fake.source).as_posix() for p in fake.source.rglob("*") if p.is_file()]
                yield {"Contents": [{"Key": k} for k in keys + ["../escape.txt", "unexpected/file.txt"]]}

        return Paginator()

    def download_file(self, bucket, key, dest):
        shutil.copyfile(self.source / key, dest)


def test_s3_sync_swaps_in_validated_artifacts_and_keeps_previous(tmp_path):
    data = tmp_path / "data"
    s = settings(tmp_path, data, AEA_S3_BUCKET="bucket")
    with TestClient(create_app(s, s3_client=FakeS3(ARTIFACTS))) as c:
        h = c.get("/api/health").json()
        assert h["s3_sync"]["state"] == "ok" and h["status"] == "ok"
    assert (data / "current" / "registry.json").is_file()
    assert not (data / "current" / "unexpected").exists()  # only allowed prefixes are synced
    with TestClient(create_app(s, s3_client=FakeS3(ARTIFACTS))):
        pass
    assert (data / "previous" / "registry.json").is_file()


def test_s3_failure_uses_cache_or_reports_no_cache(tmp_path):
    data = tmp_path / "data"
    with TestClient(create_app(settings(tmp_path, data, AEA_S3_BUCKET="b"), s3_client=FakeS3(ARTIFACTS, fail=True))) as c:
        assert c.get("/api/health").json()["s3_sync"]["state"] == "failed_no_cache"
    shutil.copytree(ARTIFACTS, data / "current")
    with TestClient(create_app(settings(tmp_path, data, AEA_S3_BUCKET="b"), s3_client=FakeS3(ARTIFACTS, fail=True))) as c:
        h = c.get("/api/health").json()
        assert h["s3_sync"]["state"] == "failed_using_cache" and h["ready"] is True


# ---- alerts (optional SNS) ------------------------------------------------------------


class FakeSNS:
    def __init__(self, fail=False):
        self.fail, self.messages = fail, []

    def publish(self, **kwargs):
        if self.fail:
            raise TimeoutError("sns timeout")
        self.messages.append(kwargs)


def test_alert_sent_then_cooldown(tmp_path):
    sns = FakeSNS()
    s = settings(tmp_path, ARTIFACTS, AEA_ALERTS_ENABLED="true", AEA_SNS_TOPIC_ARN="arn:aws:sns:ap-south-1:0:t")
    with TestClient(create_app(s, sns_client_factory=lambda: sns)) as c:
        first = c.post("/api/analyze/sample", json={"sample_id": "simulated_scenario", "bill": BILL}).json()
        second = c.post("/api/analyze/sample", json={"sample_id": "simulated_scenario", "bill": BILL}).json()
    assert first["alert"]["status"] == "sent" and second["alert"]["status"] == "cooldown"
    assert len(sns.messages) == 1
    message = sns.messages[0]["Message"]
    assert "Simulated demonstration scenario" in message and "illustrative" in message


def test_alert_failure_never_fails_the_analysis(tmp_path):
    s = settings(tmp_path, ARTIFACTS, AEA_ALERTS_ENABLED="true", AEA_SNS_TOPIC_ARN="arn:x")
    with TestClient(create_app(s, sns_client_factory=lambda: FakeSNS(fail=True))) as c:
        r = c.post("/api/analyze/sample", json={"sample_id": "simulated_scenario", "bill": BILL})
    assert r.status_code == 200 and r.json()["alert"]["status"] == "failed"


def test_alerts_need_both_flag_and_topic(tmp_path):
    s = settings(tmp_path, ARTIFACTS, AEA_ALERTS_ENABLED="true")  # no topic
    with TestClient(create_app(s, sns_client_factory=lambda: FakeSNS())) as c:
        r = c.post("/api/analyze/sample", json={"sample_id": "simulated_scenario", "bill": BILL})
    assert r.json()["alert"]["status"] == "disabled"
