"""Shared helpers for the offline ``ml/`` scripts.

Importing this module puts ``backend/`` on ``sys.path`` so the scripts reuse the exact
serving code in ``app.nilm`` / ``app.analytics`` (train/serve parity).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

ARTIFACTS_DIR = REPO_ROOT / "artifacts"
SCENARIO_PATH = REPO_ROOT / "ml" / "synthetic" / "scenarios" / "simulated_scenario.yaml"


def repo_relative(path: Path) -> str:
    """Forward-slash path relative to the repository root (stable across OSes)."""
    return Path(path).resolve().relative_to(REPO_ROOT).as_posix()


def config_sha256(path: Path) -> str:
    """Hash of a text config with line endings normalized, so a Windows checkout with
    CRLF line endings produces the same hash as Linux."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def minute_timestamps(start: pd.Timestamp, n_minutes: int) -> list[str]:
    index = pd.date_range(start=start, periods=n_minutes, freq="1min")
    return [ts.isoformat() for ts in index]


def window_csv_bytes(start: pd.Timestamp, values: np.ndarray) -> bytes:
    """Deterministic ``timestamp,power_w`` CSV bytes (LF line endings, 1 decimal,
    empty field for missing)."""
    lines = ["timestamp,power_w"]
    for ts, value in zip(minute_timestamps(start, values.size), values):
        lines.append(f"{ts}," if np.isnan(value) else f"{ts},{value:.1f}")
    return ("\n".join(lines) + "\n").encode("ascii")


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path: Path, obj: dict) -> None:
    write_bytes(path, (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def load_scenario(path: Path = SCENARIO_PATH) -> dict:
    import yaml  # offline dependency only (ml/requirements.txt)

    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
