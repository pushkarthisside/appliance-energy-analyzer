"""Write ``artifacts/registry.json`` (ARCHITECTURE.md §5).

Sources:
- ``ml/candidates.json``: real-model candidates. Their ``status`` comes ONLY from
  ``evaluation/evaluation.json`` decisions; without a recorded decision they stay
  ``candidate`` (not run). Nothing is ever promoted by hand.
- the scenario YAML: synthetic demonstration appliances (``status: demo``) with declared
  (not measured) uncertainty.

Usage: python ml/export_registry.py [--artifacts DIR]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import common  # noqa: F401  (puts backend/ on sys.path)
from common import ARTIFACTS_DIR, REPO_ROOT, SCENARIO_PATH, load_scenario, write_json

from app.nilm.registry import parse_registry

REGISTRY_VERSION = 1
WINDOW_MINUTES = 99  # frozen sequence-to-point window (ARCHITECTURE.md §8.1)


def real_entry(candidate: dict, decision: str | None) -> dict:
    if decision == "go":
        # A go entry needs the trained model's path, normalization stats and the
        # validation-derived registry values. Model training/export is not implemented
        # yet, so a go decision cannot be exported honestly.
        raise NotImplementedError(
            f"{candidate['id']} has decision 'go' but model export is not implemented; "
            "implement ml/train.py and ml/export_onnx.py first"
        )
    status = "no_go" if decision == "no_go" else "candidate"
    return {
        "id": candidate["id"],
        "name": candidate["name"],
        "class": candidate["class"],
        "provenance": "real_model",
        "status": status,
        "adapter": "onnx_seq2point",
        "model": {
            "version": None,
            "path": None,
            "window_minutes": WINDOW_MINUTES,
            "norm": {"mains_mean": None, "mains_std": None, "app_mean": None, "app_std": None},
        },
        "on_threshold_w": None,
        "driver_analysis": candidate["driver_analysis"],
        "weather_sensitive": candidate["weather_sensitive"],
        "energy_uncertainty_pct": None,
        "uncertainty_source": "validation_weeks",
        "min_excess_kwh_week": None,
        "action_id": candidate["action_id"],
        "evaluation_ref": f"real.{candidate['id']}",
    }


def synthetic_entry(appliance: dict) -> dict:
    reg = appliance["registry"]
    return {
        "id": appliance["id"],
        "name": appliance["name"],
        "class": appliance["class"],
        "provenance": "synthetic_trace",
        "status": "demo",
        "adapter": "trace",
        "model": None,
        "on_threshold_w": reg["on_threshold_w"],
        "driver_analysis": reg["driver_analysis"],
        "weather_sensitive": reg["weather_sensitive"],
        "energy_uncertainty_pct": reg["energy_uncertainty_pct"],
        "uncertainty_source": "declared",
        "min_excess_kwh_week": reg["min_excess_kwh_week"],
        "action_id": reg["action_id"],
        "evaluation_ref": None,
    }


def build_registry(artifacts: Path, scenario_path: Path = SCENARIO_PATH) -> dict:
    candidates = json.loads((REPO_ROOT / "ml" / "candidates.json").read_text(encoding="utf-8"))["candidates"]
    evaluation_path = artifacts / "evaluation" / "evaluation.json"
    decisions: dict[str, str] = {}
    if evaluation_path.is_file():
        real = json.loads(evaluation_path.read_text(encoding="utf-8")).get("real") or {}
        decisions = {app_id: result.get("decision") for app_id, result in real.items()}

    entries = [real_entry(c, decisions.get(c["id"])) for c in candidates]
    go_classes = {e["class"] for e in entries if e["status"] == "go"}
    for appliance in load_scenario(scenario_path)["appliances"]:
        if appliance["class"] in go_classes:
            raise ValueError(f"class {appliance['class']} has a go real model and must not also be simulated")
        entries.append(synthetic_entry(appliance))

    registry = {"registry_version": REGISTRY_VERSION, "interval_seconds": 60, "appliances": entries}
    parsed = parse_registry(registry)  # same validation the server runs at startup
    if parsed.entry_errors:
        raise ValueError(f"registry entries invalid: {parsed.entry_errors}")
    return registry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artifacts", type=Path, default=ARTIFACTS_DIR)
    args = parser.parse_args()
    registry = build_registry(args.artifacts)
    write_json(args.artifacts / "registry.json", registry)
    statuses = {e["id"]: e["status"] for e in registry["appliances"]}
    print(f"wrote {args.artifacts / 'registry.json'}: {statuses}")


if __name__ == "__main__":
    main()
