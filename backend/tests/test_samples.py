"""TS-I-02, TS-C-02 (bundle part) — the committed simulated_scenario bundle (§6.2-§6.3, §10)."""

import copy
import json
import shutil

import numpy as np
import pytest
from conftest import ARTIFACTS, SAMPLE_DIR

from app.analytics.constants import WINDOW_MINUTES
from app.ingest.bundle import BundleError, load_bundle
from app.nilm.registry import load_registry
from app.pipeline import run_pipeline


@pytest.fixture(scope="module")
def bundle():
    return load_bundle(SAMPLE_DIR)


def test_bundle_shape_and_three_valid_weeks(bundle):
    assert bundle.aggregate_w.shape == (WINDOW_MINUTES,)
    lines = (SAMPLE_DIR / "aggregate.csv").read_text(encoding="ascii").splitlines()
    assert lines[0] == "timestamp,power_w" and len(lines) == WINDOW_MINUTES + 1
    result = run_pipeline(bundle, load_registry(ARTIFACTS / "registry.json"), "none")
    assert all(result.total.weeks[w].valid for w in ("baseline_1", "baseline_2", "current"))


def test_fully_synthetic_fallback_is_disclosed(bundle):
    m = bundle.manifest
    assert m["sample_id"] == "simulated_scenario" and m["simulated"] is True
    assert m["aggregate_origin"] == "fully_synthetic" and m["real_base"] is None
    assert all(m["synthetic_background"][k] for k in ("script", "config", "config_sha256"))
    assert len(m["synthetic_appliances"]) >= 1
    assert "simulated" in m["description"].lower() and "not measurements" in m["description"].lower()


def test_aggregate_is_background_plus_traces(bundle):
    from common import load_scenario
    from synthetic.generate_background import generate_background

    background = generate_background(load_scenario()["background"], 21)
    reconstructed = background + sum(bundle.traces.values())
    np.testing.assert_allclose(bundle.aggregate_w, reconstructed, atol=0.051)


def test_expected_status_matches_pipeline_output(bundle):
    """Verifies code behaviour on constructed data; NOT detection performance."""
    result = run_pipeline(bundle, load_registry(ARTIFACTS / "registry.json"), "none")
    observed = {a.entry.id: a.flag.status for a in result.appliances}
    for app in bundle.manifest["synthetic_appliances"]:
        assert observed[app["id"]] == app["expected_status"]
    drivers = {a.entry.id: a.driver for a in result.appliances}
    assert drivers == {"air_conditioner_sim": "longer_operating_time", "water_heater_sim": "higher_power_when_on"}


def test_real_models_are_never_invoked_on_fully_synthetic_bundle(bundle):
    """Even with a go model loaded and passed in, a fully synthetic bundle never runs it."""
    from test_registry import DEMO, GO, registry

    from app.nilm.registry import parse_registry

    class NeverCalled:
        def predict(self, mains):
            raise AssertionError("real-model inference must not run on a fully synthetic bundle")

    water = {**DEMO, "id": "water_heater_sim", "class": "water_heater"}
    reg = parse_registry(registry(DEMO, water, {**GO, "class": "fridge", "id": "fridge"}))
    result = run_pipeline(bundle, reg, "none", real_adapters={"fridge": NeverCalled()})
    assert {a.entry.id for a in result.appliances} == {"air_conditioner_sim", "water_heater_sim"}
    assert result.unavailable == []


def _copy_bundle(tmp_path):
    target = tmp_path / "simulated_scenario"
    shutil.copytree(SAMPLE_DIR, target)
    return target


def test_tampered_aggregate_is_rejected(tmp_path):
    target = _copy_bundle(tmp_path)
    with open(target / "aggregate.csv", "ab") as f:
        f.write(b"\n")
    with pytest.raises(BundleError, match="aggregate_sha256"):
        load_bundle(target)


@pytest.mark.parametrize(
    "change",
    [
        {"real_base": {"source": "iAWE", "split": "train"}},  # never training data
        {"synthetic_background": None},
        {"simulated": False},
        {"synthetic_appliances": []},
        {"window": {"start": "2026-04-06T00:00:00+05:30", "days": 14}},
    ],
)
def test_invalid_manifests_are_rejected(tmp_path, change):
    target = _copy_bundle(tmp_path)
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    manifest = {**copy.deepcopy(manifest), **change}
    (target / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(BundleError):
        load_bundle(target)
