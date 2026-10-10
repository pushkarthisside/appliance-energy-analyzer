"""TS-I-01, 03, 04, 05 and §9/§11.5 field rules for run_pipeline + apply_bill."""

import json
from dataclasses import replace

import numpy as np
import pytest
from conftest import ARTIFACTS, SAMPLE_DIR

from app.analytics.constants import WEEK_MINUTES
from app.ingest.bundle import load_bundle
from app.nilm.registry import load_registry, parse_registry
from app.pipeline import apply_bill, run_pipeline
from app.schemas import AnalysisResponse

ACTIONS = json.loads((ARTIFACTS / "config" / "actions.json").read_text(encoding="utf-8"))
REGISTRY_JSON = json.loads((ARTIFACTS / "registry.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bundle():
    return load_bundle(SAMPLE_DIR)


@pytest.fixture(scope="module")
def result(bundle):
    return run_pipeline(bundle, load_registry(ARTIFACTS / "registry.json"), "none")


def respond(result, amount=4200, units=500, **kwargs):
    return apply_bill(result, amount, units, ACTIONS, **kwargs).model_dump(mode="json")


def test_response_validates_against_the_api_schema(result):
    response = apply_bill(result, 4200, 500, ACTIONS)
    assert isinstance(response, AnalysisResponse)
    assert response.source.simulated is True
    assert response.source.evidence_level == "none"


def test_energy_and_cost_reconcile(result):
    r = respond(result)
    total = r["summary"]["total_kwh_period"]
    assert sum(a["kwh_period"] for a in r["appliances"]) == pytest.approx(total, rel=1e-3)
    assert sum(a["share_pct"] for a in r["appliances"]) == pytest.approx(100.0, abs=0.05)
    assert r["cost"]["effective_rate_inr_per_kwh"] == pytest.approx(8.4)
    assert r["summary"]["estimated_cost_period_inr"] == pytest.approx(round(total * 8.4), abs=1)


def test_series_lengths(result):
    r = respond(result)
    assert len(r["signals"]["aggregate_w"]) == 672
    assert set(r["signals"]["by_appliance"]) == {"air_conditioner_sim", "water_heater_sim", "other"}
    assert all(len(v) == 672 for v in r["signals"]["by_appliance"].values())
    for a in r["appliances"]:
        assert len(a["daily_kwh"]) == (0 if a["id"] == "other" else 21)


def test_other_is_never_flagged_and_issues_are_ranked(result):
    r = respond(result)
    other = next(a for a in r["appliances"] if a["id"] == "other")
    assert other["provenance"] == "residual" and other["status"] is None
    assert all(i["appliance_id"] != "other" for i in r["issues"])
    mids = [i["savings"]["inr_per_month"]["mid"] for i in r["issues"]]
    assert mids == sorted(mids, reverse=True)
    assert [i["rank"] for i in r["issues"]] == list(range(1, len(mids) + 1))


def test_synthetic_issues_are_illustrative_without_emissions(result):
    emissions = {
        "factor_kg_co2e_per_kwh": 0.7, "source_name": "x", "source_url": "https://example.org",
        "edition": "x", "publication_year": 2025, "geography": "India", "retrieved_on": "2026-10-10",
        "verified_by": "x",
    }
    r = respond(result, emissions=emissions)
    assert r["issues"]
    for issue in r["issues"]:
        assert issue["basis"] == "synthetic_trace"
        assert issue["savings"]["illustrative"] is True
        assert issue["savings"]["kg_co2e_per_month"] is None  # synthetic never feeds emissions
        assert issue["savings"]["label"] == ACTIONS["savings_label"]


def test_incomplete_emissions_config_is_treated_as_absent(result):
    assert respond(result, emissions={"factor_kg_co2e_per_kwh": 0.7})["emissions"] is None


def test_deterministic_apart_from_id_and_timestamp(result):
    a, b = respond(result), respond(result)
    for r in (a, b):
        r.pop("analysis_id")
        r.pop("generated_at")
    assert a == b


def test_invalid_bill_raises(result):
    for amount, units in ((0, 500), (4200, float("nan")), (-1, 10), (4200, 10_000_001)):
        with pytest.raises(ValueError, match="invalid_bill"):
            apply_bill(result, amount, units, ACTIONS)


def test_unusual_rate_adds_a_warning(result):
    codes = [w["code"] for w in respond(result, amount=60_000, units=500)["warnings"]]
    assert codes == ["bill_rate_unusual"]


def test_alert_status_defaults_and_override(result):
    assert respond(result)["alert"]["status"] == "disabled"
    assert respond(result, alert_status="cooldown")["alert"]["status"] == "cooldown"


def test_unregistered_synthetic_appliance_falls_into_other_with_warning(bundle, result):
    reduced = dict(REGISTRY_JSON, appliances=[a for a in REGISTRY_JSON["appliances"] if a["id"] != "water_heater_sim"])
    r = respond(run_pipeline(bundle, parse_registry(reduced), "none"))
    ids = [a["id"] for a in r["appliances"]]
    assert "water_heater_sim" not in ids
    assert [w["code"] for w in r["warnings"]] == ["appliance_unavailable"]
    full_other = next(a for a in respond(result)["appliances"] if a["id"] == "other")["kwh_period"]
    new_other = next(a for a in r["appliances"] if a["id"] == "other")["kwh_period"]
    assert new_other > full_other


def test_no_issues_gives_empty_state(bundle):
    calm = json.loads(json.dumps(REGISTRY_JSON))
    for entry in calm["appliances"]:
        if entry["status"] == "demo":
            entry["energy_uncertainty_pct"] = 100.0  # T = 2.0, nothing exceeds it
    r = respond(run_pipeline(bundle, parse_registry(calm), "none"))
    assert r["issues"] == [] and r["summary"]["issues_count"] == 0
    assert r["alert"]["status"] == "no_issues"
    assert {a["status"] for a in r["appliances"] if a["id"] != "other"} == {"typical"}


def test_missing_current_week_gives_insufficient_data_and_no_issue(bundle):
    broken = replace(bundle, aggregate_w=bundle.aggregate_w.copy())
    broken.aggregate_w[2 * WEEK_MINUTES : 2 * WEEK_MINUTES + 3000] = np.nan  # ~30 % of the current week
    r = respond(run_pipeline(broken, load_registry(ARTIFACTS / "registry.json"), "none"))
    statuses = {a["id"]: (a["status"], a["status_reason"]) for a in r["appliances"] if a["id"] != "other"}
    assert set(statuses.values()) == {("insufficient_data", "current_week_invalid")}
    assert r["issues"] == []
    assert all(a["weekly_kwh"]["current"] is None for a in r["appliances"])
    assert r["period"]["weeks"]["current"]["valid"] is False
