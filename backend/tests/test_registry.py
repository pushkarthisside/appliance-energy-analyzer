"""TS-U-12 — provenance/status/adapter combinations and null-field rules (§5)."""

import copy
import json

import pytest
from conftest import ARTIFACTS

from app.nilm.registry import RegistryError, load_registry, parse_registry

DEMO = {
    "id": "air_conditioner_sim", "name": "Air conditioner", "class": "air_conditioner",
    "provenance": "synthetic_trace", "status": "demo", "adapter": "trace", "model": None,
    "on_threshold_w": 150.0, "driver_analysis": True, "weather_sensitive": True,
    "energy_uncertainty_pct": 15.0, "uncertainty_source": "declared", "min_excess_kwh_week": 1.0,
    "action_id": "reduce_runtime", "evaluation_ref": None,
}
GO = {
    "id": "air_conditioner", "name": "Air conditioner", "class": "air_conditioner",
    "provenance": "real_model", "status": "go", "adapter": "onnx_seq2point",
    "model": {"version": "v1", "path": "models/air_conditioner/v1/model.onnx", "window_minutes": 99,
              "norm": {"mains_mean": 1.0, "mains_std": 1.0, "app_mean": 1.0, "app_std": 1.0}},
    "on_threshold_w": 150.0, "driver_analysis": True, "weather_sensitive": True,
    "energy_uncertainty_pct": 20.0, "uncertainty_source": "validation_weeks", "min_excess_kwh_week": 1.0,
    "action_id": "reduce_runtime", "evaluation_ref": "real.air_conditioner",
}


def registry(*entries):
    return {"registry_version": 1, "interval_seconds": 60, "appliances": list(entries)}


def with_(entry, **changes):
    out = copy.deepcopy(entry)
    out.update(changes)
    return out


def test_committed_registry_is_valid_and_has_no_go_without_evaluation():
    reg = load_registry(ARTIFACTS / "registry.json")
    assert reg.entry_errors == {}
    statuses = {e.id: e.status for e in reg.entries.values()}
    assert all(statuses[i] == "candidate" for i in ("air_conditioner", "fridge", "washing_machine"))
    assert statuses["air_conditioner_sim"] == statuses["water_heater_sim"] == "demo"
    evaluation = json.loads((ARTIFACTS / "evaluation" / "evaluation.json").read_text(encoding="utf-8"))
    assert evaluation["real"] == {} and evaluation["evidence_level"] == "none"


def test_valid_demo_and_go_entries_are_runnable():
    reg = parse_registry(registry(DEMO, GO))
    assert set(reg.runnable()) == {"air_conditioner_sim", "air_conditioner"}


@pytest.mark.parametrize(
    "bad",
    [
        with_(DEMO, status="go"),
        with_(DEMO, adapter="onnx_seq2point"),
        with_(GO, status="demo"),
        with_(GO, adapter="trace"),
        with_(DEMO, model={"path": "x"}),
    ],
)
def test_invalid_combinations_are_entry_errors(bad):
    reg = parse_registry(registry(bad))
    assert bad["id"] in reg.entry_errors and bad["id"] not in reg.entries


@pytest.mark.parametrize(
    "bad",
    [
        with_(GO, energy_uncertainty_pct=None),
        with_(GO, min_excess_kwh_week=None),
        with_(GO, on_threshold_w=None),
        with_(GO, model={**GO["model"], "norm": {**GO["model"]["norm"], "app_std": None}}),
        with_(DEMO, energy_uncertainty_pct=None),
    ],
)
def test_runnable_entries_with_null_required_fields_are_rejected(bad):
    assert bad["id"] in parse_registry(registry(bad)).entry_errors


def test_candidate_with_nulls_is_fine_but_not_runnable():
    candidate = with_(GO, status="candidate", energy_uncertainty_pct=None, model=None)
    reg = parse_registry(registry(candidate))
    assert reg.entry_errors == {} and reg.runnable() == {}


@pytest.mark.parametrize("bad_id", ["other", "AC", "a", "1ac", "air-conditioner"])
def test_bad_ids_make_the_registry_invalid(bad_id):
    with pytest.raises(RegistryError):
        parse_registry(registry(with_(DEMO, id=bad_id)))


def test_duplicate_ids_make_the_registry_invalid():
    with pytest.raises(RegistryError):
        parse_registry(registry(DEMO, DEMO))
