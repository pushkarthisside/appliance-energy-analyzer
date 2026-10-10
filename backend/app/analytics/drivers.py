"""Likely driver of an unusual week (ARCHITECTURE.md §9.4). States an association only."""

from __future__ import annotations

import statistics

from app.analytics.constants import DRIVER_MIN_RATIO
from app.analytics.weekly import SeriesStats


def likely_driver(stats: SeriesStats, status: str, driver_analysis: bool) -> str | None:
    """Return ``longer_operating_time``, ``higher_power_when_on``, ``unclear`` or ``None``.

    ``None`` when the appliance is not unusual, driver analysis is off, or any required
    statistic is missing or a baseline is not positive.
    """
    if status != "unusual" or not driver_analysis:
        return None
    w = stats.weeks
    values = [
        w["current"].on_hours,
        w["baseline_1"].on_hours,
        w["baseline_2"].on_hours,
        w["current"].avg_on_power_w,
        w["baseline_1"].avg_on_power_w,
        w["baseline_2"].avg_on_power_w,
    ]
    if any(v is None for v in values):
        return None
    base_hours = statistics.median([w["baseline_1"].on_hours, w["baseline_2"].on_hours])
    base_power = statistics.median([w["baseline_1"].avg_on_power_w, w["baseline_2"].avg_on_power_w])
    if base_hours <= 0 or base_power <= 0:
        return None

    r_time = w["current"].on_hours / base_hours
    r_power = w["current"].avg_on_power_w / base_power
    if r_time >= r_power and r_time >= DRIVER_MIN_RATIO:
        return "longer_operating_time"
    if r_power > r_time and r_power >= DRIVER_MIN_RATIO:
        return "higher_power_when_on"
    return "unclear"
