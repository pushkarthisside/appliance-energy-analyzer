"""Possible-savings heuristic range (ARCHITECTURE.md §9.5).

A heuristic sensitivity range, not a calibrated confidence interval: possible savings
if use returned to the preceding weeks' level. Never a forecast or a measured reduction.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analytics.constants import DAYS_PER_MONTH, WEEK_DAYS


@dataclass(frozen=True)
class KwhRange:
    low: float
    mid: float
    high: float

    def scaled(self, factor: float) -> "KwhRange":
        return KwhRange(self.low * factor, self.mid * factor, self.high * factor)


def savings_kwh_month(excess_kwh_week: float, energy_uncertainty_pct: float) -> KwhRange:
    """mid = excess × 30/7; low = max(0, mid(1−e)); high = mid(1+e). Unrounded."""
    e = energy_uncertainty_pct / 100.0
    mid = excess_kwh_week * DAYS_PER_MONTH / WEEK_DAYS
    return KwhRange(low=max(0.0, mid * (1 - e)), mid=mid, high=mid * (1 + e))
