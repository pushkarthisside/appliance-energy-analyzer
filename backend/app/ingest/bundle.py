"""Sample bundle loading and validation (ARCHITECTURE.md §6.2-§6.3, §10).

A bundle is ``samples/{sample_id}/`` containing ``manifest.json``, ``aggregate.csv``
and ``synthetic/{appliance_id}.csv`` traces. Any violation raises ``BundleError``,
which the startup code reports as a failed sample.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from app.analytics.constants import WINDOW_DAYS, WINDOW_MINUTES
from app.nilm.preprocess import LOCAL_TZ, clean_power, read_power_frame, window_start

SAMPLE_IDS = ("typical_period", "simulated_scenario")
AGGREGATE_ORIGINS = ("real_base_plus_synthetic", "fully_synthetic")
REAL_BASE_SPLITS = ("validation", "test")


class BundleError(ValueError):
    """The sample bundle is invalid and must not be served."""


@dataclass
class Bundle:
    sample_id: str
    manifest: dict
    start: pd.Timestamp
    aggregate_w: np.ndarray  # float64[30 240], NaN = missing
    traces: dict[str, np.ndarray] = field(default_factory=dict)  # synthetic appliance id -> watts

    @property
    def fully_synthetic(self) -> bool:
        return self.manifest["aggregate_origin"] == "fully_synthetic"

    @property
    def synthetic_ids(self) -> list[str]:
        return [a["id"] for a in self.manifest.get("synthetic_appliances", [])]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_window_csv(path: Path, start: pd.Timestamp) -> np.ndarray:
    """Read a bundle CSV and enforce §6.2 exactly: 30 240 rows, 1-minute spacing from
    local midnight ``start``, empty ``power_w`` meaning missing. No resampling is needed
    or allowed; a CSV that does not match the grid is rejected."""
    try:
        frame = read_power_frame(path)
    except (OSError, ValueError) as exc:
        raise BundleError(f"{path.name}: {exc}") from exc
    if len(frame) != WINDOW_MINUTES:
        raise BundleError(f"{path.name}: expected {WINDOW_MINUTES} rows, found {len(frame)}")
    series = clean_power(frame)
    expected = pd.date_range(start=start, periods=WINDOW_MINUTES, freq="1min", tz=LOCAL_TZ)
    if len(series) != WINDOW_MINUTES or not series.index.equals(expected):
        raise BundleError(f"{path.name}: timestamps are not a 1-minute grid starting at {start.isoformat()}")
    return series.to_numpy(dtype="float64")


def _validate_manifest(manifest: dict, sample_id: str) -> None:
    def fail(msg: str) -> None:
        raise BundleError(f"manifest for {sample_id}: {msg}")

    if manifest.get("schema_version") != 1:
        fail("schema_version must be 1")
    if manifest.get("sample_id") != sample_id or sample_id not in SAMPLE_IDS:
        fail("sample_id does not match the bundle directory or is not canonical")
    if (manifest.get("window") or {}).get("days") != WINDOW_DAYS:
        fail(f"window.days must be {WINDOW_DAYS}")
    origin = manifest.get("aggregate_origin")
    if origin not in AGGREGATE_ORIGINS:
        fail("aggregate_origin is invalid")

    synthetic = manifest.get("synthetic_appliances") or []
    if origin == "real_base_plus_synthetic":
        real_base = manifest.get("real_base")
        if not isinstance(real_base, dict) or real_base.get("split") not in REAL_BASE_SPLITS:
            fail("real_base is required and its split must be validation or test, never train")
        if manifest.get("synthetic_background") is not None:
            fail("synthetic_background must be null for a real base")
    else:
        if manifest.get("real_base") is not None:
            fail("fully_synthetic bundles must have real_base null")
        bg = manifest.get("synthetic_background")
        if not isinstance(bg, dict) or not all(bg.get(k) for k in ("script", "config", "config_sha256")) or "seed" not in bg:
            fail("fully_synthetic bundles need synthetic_background generator metadata")

    expected_simulated = bool(synthetic) or origin == "fully_synthetic"
    if manifest.get("simulated") is not expected_simulated:
        fail("simulated must be true iff there are synthetic appliances or the aggregate is fully synthetic")
    if sample_id == "simulated_scenario" and not synthetic:
        fail("simulated_scenario must contain at least one synthetic appliance trace")
    if sample_id == "typical_period" and (synthetic or origin == "fully_synthetic"):
        fail("typical_period must be real data without synthetic appliances")
    for app in synthetic:
        if not app.get("id") or not app.get("trace") or app.get("expected_status") not in ("typical", "unusual", "insufficient_data"):
            fail("each synthetic appliance needs id, trace and expected_status")
    if not manifest.get("aggregate_sha256"):
        fail("aggregate_sha256 is required")


def load_bundle(sample_dir: str | Path) -> Bundle:
    sample_dir = Path(sample_dir)
    sample_id = sample_dir.name
    try:
        manifest = json.loads((sample_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BundleError(f"cannot read manifest for {sample_id}: {exc}") from exc
    _validate_manifest(manifest, sample_id)

    try:
        start = window_start(manifest["window"]["start"])
    except (KeyError, ValueError) as exc:
        raise BundleError(f"manifest for {sample_id}: invalid window.start ({exc})") from exc

    aggregate_path = sample_dir / "aggregate.csv"
    if not aggregate_path.is_file():
        raise BundleError(f"{sample_id}: aggregate.csv is missing")
    if sha256_file(aggregate_path) != manifest["aggregate_sha256"]:
        raise BundleError(f"{sample_id}: aggregate.csv does not match aggregate_sha256")
    aggregate = read_window_csv(aggregate_path, start)

    traces = {}
    for app in manifest.get("synthetic_appliances") or []:
        trace_path = (sample_dir / app["trace"]).resolve()
        if sample_dir.resolve() not in trace_path.parents or not trace_path.is_file():
            raise BundleError(f"{sample_id}: trace for {app['id']} is missing or outside the bundle")
        traces[app["id"]] = read_window_csv(trace_path, start)

    return Bundle(sample_id=sample_id, manifest=manifest, start=start, aggregate_w=aggregate, traces=traces)
