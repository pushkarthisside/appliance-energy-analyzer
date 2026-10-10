"""Write ``artifacts/evaluation/evaluation.json`` (ARCHITECTURE.md §6.6, §12).

Current scope (honest by construction):
- The iAWE data audit, chronological split and real-model training are NOT implemented
  yet, so no real appliance model is evaluated. The file records
  ``evidence_level: "none"``, null split boundaries, an empty ``real`` object and an
  explicit ``no_evaluation_reason``. No metric, date or decision is fabricated.
- ``synthetic.pipeline_checks`` records expected vs observed status for the constructed
  ``simulated_scenario`` bundle. These checks verify code behaviour on constructed data;
  they are not accuracy or detection-rate evidence.

Usage: python ml/evaluate.py [--artifacts DIR]
       (``--data`` for real-model evaluation is reserved for T-404 and not implemented.)
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import common  # noqa: F401  (puts backend/ on sys.path)
from common import ARTIFACTS_DIR, REPO_ROOT, config_sha256, write_json

from app.ingest.bundle import load_bundle
from app.nilm.registry import load_registry
from app.pipeline import run_pipeline

NO_EVALUATION_REASON = (
    "The iAWE data audit, chronological split and real-model training have not been run yet, "
    "so no real appliance model has been evaluated."
)


def code_version() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
        )
        return out.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def synthetic_pipeline_checks(artifacts: Path) -> list[dict]:
    registry = load_registry(artifacts / "registry.json")
    checks = []
    for sample_dir in sorted((artifacts / "samples").iterdir()):
        if not (sample_dir / "manifest.json").is_file():
            continue
        bundle = load_bundle(sample_dir)
        if not bundle.synthetic_ids:
            continue
        result = run_pipeline(bundle, registry, evidence_level="none")
        observed = {a.entry.id: a.flag.status for a in result.appliances}
        for app in bundle.manifest["synthetic_appliances"]:
            checks.append(
                {
                    "sample_id": bundle.sample_id,
                    "appliance_id": app["id"],
                    "expected_status": app["expected_status"],
                    "observed_status": observed.get(app["id"]),
                }
            )
    return checks


def build_evaluation(artifacts: Path) -> dict:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "code_version": code_version(),
        "criteria_sha256": config_sha256(REPO_ROOT / "ml" / "go_criteria.json"),
        "dataset": {"name": "iAWE", "audit_ref": None},
        "evidence_level": "none",
        "no_evaluation_reason": NO_EVALUATION_REASON,
        "splits": {"gap_days": 1, "gap_dates": [], "train": None, "validation": None, "test": None},
        "real": {},
        "scenario_checks": [],
        "unmodified_window_check": {"go_appliances_checked": 0, "unusual_flags": 0},
        "synthetic": {"pipeline_checks": synthetic_pipeline_checks(artifacts)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artifacts", type=Path, default=ARTIFACTS_DIR)
    parser.add_argument("--data", type=Path, default=None, help="iAWE data directory (not implemented yet)")
    args = parser.parse_args()
    if args.data is not None:
        raise SystemExit("Real-model evaluation (T-404) is not implemented yet; run without --data.")
    evaluation = build_evaluation(args.artifacts)
    write_json(args.artifacts / "evaluation" / "evaluation.json", evaluation)
    checks = evaluation["synthetic"]["pipeline_checks"]
    mismatched = [c for c in checks if c["expected_status"] != c["observed_status"]]
    print(f"wrote evaluation.json: evidence_level=none, {len(checks)} synthetic pipeline check(s), {len(mismatched)} mismatch(es)")
    if mismatched:
        raise SystemExit(f"synthetic pipeline checks failed: {json.dumps(mismatched)}")


if __name__ == "__main__":
    main()
