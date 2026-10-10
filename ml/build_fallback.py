"""Build the complete P0 fallback artifact set in ``artifacts/`` in the right order.

    python ml/build_fallback.py

1. registry.json      (candidates stay ``candidate``; synthetic appliances are ``demo``)
2. samples/           (``simulated_scenario`` fully synthetic; ``typical_period`` only with a go model)
3. evaluation.json    (``evidence_level: none`` + synthetic pipeline checks)
4. registry.json      (re-exported from the evaluation decisions; unchanged today)

Then upload ``artifacts/`` to S3 (see ARCHITECTURE.md §6.1, §18.1).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import common  # noqa: F401
from common import ARTIFACTS_DIR, write_json

import evaluate
import export_registry
import make_samples


def build(artifacts: Path) -> None:
    write_json(artifacts / "registry.json", export_registry.build_registry(artifacts))
    print("1/4 registry.json written")
    out = make_samples.build_simulated_scenario(artifacts)
    print(f"2/4 {out.relative_to(artifacts)} written; {make_samples.handle_typical_period(artifacts)}")
    evaluation = evaluate.build_evaluation(artifacts)
    write_json(artifacts / "evaluation" / "evaluation.json", evaluation)
    checks = evaluation["synthetic"]["pipeline_checks"]
    bad = [c for c in checks if c["expected_status"] != c["observed_status"]]
    print(f"3/4 evaluation.json written: evidence_level=none, {len(checks)} pipeline checks, {len(bad)} mismatches")
    write_json(artifacts / "registry.json", export_registry.build_registry(artifacts))
    print("4/4 registry.json re-exported")
    if bad:
        raise SystemExit(f"synthetic pipeline checks failed: {bad}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--artifacts", type=Path, default=ARTIFACTS_DIR)
    build(parser.parse_args().artifacts)


if __name__ == "__main__":
    main()
