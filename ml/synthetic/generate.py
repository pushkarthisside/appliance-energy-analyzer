"""Deterministic synthetic appliance traces (ARCHITECTURE.md §10.3).

Each appliance is defined in the scenario YAML: daily ON windows, power, noise, a fixed
seed and an optional current-week change:

- ``extra_minutes_per_day``: the first ON window runs longer in the current week
  (expected driver ``longer_operating_time``);
- ``power_multiplier``: the same hours at higher power in the current week
  (expected driver ``higher_power_when_on``).

Same config + same seed -> byte-identical CSV. The output is constructed data with known
ground truth, never a model prediction.
"""

from __future__ import annotations

import numpy as np

from app.analytics.constants import MINUTES_PER_DAY, WEEK_DAYS


def _minute_of_day(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def on_mask_for_day(on_windows: list[dict], extra_minutes: int = 0) -> np.ndarray:
    """Boolean mask of the ON minutes in one day. ``extra_minutes`` extends the first window."""
    mask = np.zeros(MINUTES_PER_DAY, dtype=bool)
    for i, window in enumerate(on_windows):
        start = _minute_of_day(window["start"])
        duration = int(window["duration_minutes"]) + (extra_minutes if i == 0 else 0)
        end = start + duration
        if not (0 <= start < MINUTES_PER_DAY) or end > MINUTES_PER_DAY or duration <= 0:
            raise ValueError(f"ON window {window} (+{extra_minutes} min) must stay within one day")
        mask[start:end] = True
    return mask


def generate_trace(appliance: dict, days: int) -> np.ndarray:
    """Watts for every minute of ``days`` days; the last 7 days are the current week."""
    rng = np.random.Generator(np.random.PCG64(int(appliance["seed"])))
    change = appliance.get("current_week_change") or {}
    extra = int(change.get("extra_minutes_per_day", 0))
    multiplier = float(change.get("power_multiplier", 1.0))
    current_from_day = days - WEEK_DAYS

    noise = rng.normal(0.0, float(appliance["noise_std_w"]), size=days * MINUTES_PER_DAY)
    trace = np.zeros(days * MINUTES_PER_DAY, dtype="float64")
    for day in range(days):
        in_current = day >= current_from_day
        mask = on_mask_for_day(appliance["on_windows"], extra if in_current else 0)
        power = float(appliance["power_w"]) * (multiplier if in_current else 1.0)
        sl = slice(day * MINUTES_PER_DAY, (day + 1) * MINUTES_PER_DAY)
        day_values = np.where(mask, power + noise[sl], 0.0)
        trace[sl] = day_values
    # Round to the stored precision so in-memory and on-disk values are identical.
    return np.round(np.clip(trace, 0.0, None), 1)
