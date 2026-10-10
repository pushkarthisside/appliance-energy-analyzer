"""Status, baseline and flag rule (ARCHITECTURE.md §9.2-§9.3)."""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from app.analytics.constants import (
    FLAG_ERROR_MULTIPLIER,
    FLAG_THRESHOLD_FLOOR,
    MIN_BASELINE_KWH_WEEK,
)
from app.analytics.weekly import SeriesStats


@dataclass(frozen=True)
class FlagResult:
    status: str  # typical | unusual | insufficient_data
    status_reason: str | None  # current_week_invalid | baseline_week_invalid | baseline_too_small
    baseline_kwh: float | None
    current_kwh: float | None
    excess_kwh: float | None
    change_pct: float | None  # null whenever status is insufficient_data
    threshold: float  # T as a fraction


def threshold(energy_uncertainty_pct: float) -> float:
    """T = max(FLAG_THRESHOLD_FLOOR, FLAG_ERROR_MULTIPLIER × e)."""
    e = energy_uncertainty_pct / 100.0
    return max(FLAG_THRESHOLD_FLOOR, FLAG_ERROR_MULTIPLIER * e)


def evaluate_status(
    stats: SeriesStats, energy_uncertainty_pct: float, min_excess_kwh_week: float
) -> FlagResult:
    """Evaluate the §9.2 rows in order; the first match wins."""
    t = threshold(energy_uncertainty_pct)
    b1, b2, cur = stats.weeks["baseline_1"], stats.weeks["baseline_2"], stats.weeks["current"]

    if not cur.valid or cur.kwh is None:
        return FlagResult("insufficient_data", "current_week_invalid", None, None, None, None, t)
    if not (b1.valid and b2.valid) or b1.kwh is None or b2.kwh is None:
        return FlagResult("insufficient_data", "baseline_week_invalid", None, cur.kwh, None, None, t)

    baseline = statistics.median([b1.kwh, b2.kwh])  # equals their mean
    if baseline < MIN_BASELINE_KWH_WEEK:
        return FlagResult("insufficient_data", "baseline_too_small", baseline, cur.kwh, None, None, t)

    excess = cur.kwh - baseline
    change_pct = excess / baseline * 100.0
    unusual = cur.kwh > baseline * (1 + t) and excess > min_excess_kwh_week
    return FlagResult("unusual" if unusual else "typical", None, baseline, cur.kwh, excess, change_pct, t)
