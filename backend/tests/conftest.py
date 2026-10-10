"""Test setup: make ``app`` (backend/) and the offline ``ml/`` scripts importable.

Works with both ``pytest`` and ``python -m pytest`` run from ``backend/``.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
for path in (BACKEND_DIR, REPO_ROOT / "ml"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

ARTIFACTS = REPO_ROOT / "artifacts"
SAMPLE_DIR = ARTIFACTS / "samples" / "simulated_scenario"
