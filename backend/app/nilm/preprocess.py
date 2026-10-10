"""Minute grid, week validity and missing-minute scaling (ARCHITECTURE.md §7).

Rules that matter:
- Resample to 1-minute MEAN; empty bins stay missing (NaN).
- No interpolation or imputation, ever.
- Energy is computed from valid minutes and scaled to the block length (§7.4).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.analytics.constants import (
    MAX_VALID_POWER_W,
    MIN_DAY_FRACTION,
    MIN_VALID_FRACTION,
    MINUTES_PER_DAY,
    WEEK_MINUTES,
    WEEK_NAMES,
    WINDOW_MINUTES,
)

LOCAL_TZ = "Asia/Kolkata"


def read_power_frame(source: str | Path | bytes | io.BytesIO) -> pd.DataFrame:
    """Read a ``timestamp,power_w`` CSV into a frame with a tz-aware index.

    Raises ``ValueError`` if a required column is missing.
    """
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    frame = pd.read_csv(source, dtype={"timestamp": str})
    missing = {"timestamp", "power_w"} - set(frame.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    return frame[["timestamp", "power_w"]]


def clean_power(frame: pd.DataFrame) -> pd.Series:
    """§7.2 steps 1-2: parse timestamps, convert power, mark invalid values missing.

    Returns a float Series indexed by tz-aware (Asia/Kolkata) timestamps, sorted.
    Rows whose timestamp cannot be parsed are dropped.
    """
    ts = pd.to_datetime(frame["timestamp"], errors="coerce", utc=False, format="ISO8601")
    # Naive timestamps are local time; aware ones are converted to local time.
    if getattr(ts.dt, "tz", None) is None:
        ts = ts.dt.tz_localize(LOCAL_TZ, ambiguous="NaT", nonexistent="NaT")
    else:
        ts = ts.dt.tz_convert(LOCAL_TZ)
    power = pd.to_numeric(frame["power_w"], errors="coerce").astype("float64")
    invalid = ~np.isfinite(power) | (power < 0) | (power > MAX_VALID_POWER_W)
    power = power.mask(invalid)
    series = pd.Series(power.to_numpy(), index=pd.DatetimeIndex(ts))
    series = series[series.index.notna()]
    return series.sort_index()


def to_minute_grid(series: pd.Series, start: pd.Timestamp, n_minutes: int) -> np.ndarray:
    """§7.2 step 3: duplicates averaged, 1-minute mean bins labelled by bin start.

    Returns a float64 array of length ``n_minutes`` starting at ``start``.
    Empty bins are NaN. Nothing is interpolated.
    """
    if start.tzinfo is None:
        start = start.tz_localize(LOCAL_TZ)
    else:
        start = start.tz_convert(LOCAL_TZ)
    # mean() over each 1-minute bin ignores NaN values; a bin with no valid value is NaN.
    binned = series.resample("1min", label="left", closed="left").mean()
    index = pd.date_range(start=start, periods=n_minutes, freq="1min")
    return binned.reindex(index).to_numpy(dtype="float64")


def window_start(value: str) -> pd.Timestamp:
    """Parse a manifest window start (local midnight, ISO-8601 with offset)."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize(LOCAL_TZ)
    else:
        ts = ts.tz_convert(LOCAL_TZ)
    if (ts.hour, ts.minute, ts.second, ts.microsecond) != (0, 0, 0, 0):
        raise ValueError("window start must be local midnight")
    return ts


def coverage(values: np.ndarray) -> float:
    """Fraction of valid (non-NaN) minutes."""
    if values.size == 0:
        return 0.0
    return float(np.count_nonzero(~np.isnan(values)) / values.size)


def is_valid_block(values: np.ndarray) -> bool:
    """A week or window is valid iff coverage >= 80 % (§7.3)."""
    return coverage(values) >= MIN_VALID_FRACTION


def week_slices() -> dict[str, slice]:
    """baseline_1 = days 1-7, baseline_2 = days 8-14, current = days 15-21 (§7.1)."""
    return {name: slice(i * WEEK_MINUTES, (i + 1) * WEEK_MINUTES) for i, name in enumerate(WEEK_NAMES)}


def block_kwh(values: np.ndarray, block_hours: float) -> float | None:
    """kWh of a block from its valid minutes, scaled to the block length (§7.4).

    ``None`` when the block has no valid minute.
    """
    valid = values[~np.isnan(values)]
    if valid.size == 0:
        return None
    return float(valid.mean() * block_hours / 1000.0)


def block_on_stats(
    values: np.ndarray, on_threshold_w: float, block_hours: float
) -> tuple[float | None, float | None]:
    """(on_hours, avg_on_power_w) of a block (§7.4). ON means power >= threshold."""
    valid = values[~np.isnan(values)]
    if valid.size == 0:
        return None, None
    on = valid[valid >= on_threshold_w]
    on_hours = float(on.size / valid.size * block_hours)
    avg_on_power = float(on.mean()) if on.size else None
    return on_hours, avg_on_power


def daily_kwh(values: np.ndarray, start: pd.Timestamp) -> list[dict]:
    """One entry per local day; ``kwh`` is null when the day's coverage is below 50 %."""
    days = values.size // MINUTES_PER_DAY
    result = []
    for d in range(days):
        day = values[d * MINUTES_PER_DAY : (d + 1) * MINUTES_PER_DAY]
        date = (start + pd.Timedelta(days=d)).strftime("%Y-%m-%d")
        kwh = block_kwh(day, 24) if coverage(day) >= MIN_DAY_FRACTION else None
        result.append({"date": date, "kwh": kwh})
    return result


@dataclass(frozen=True)
class WindowGrid:
    """A 21-day window on the 1-minute grid."""

    start: pd.Timestamp
    values: np.ndarray  # float64[30 240], NaN = missing

    def __post_init__(self) -> None:
        if self.values.shape != (WINDOW_MINUTES,):
            raise ValueError(f"window must have {WINDOW_MINUTES} minutes, got {self.values.shape}")
