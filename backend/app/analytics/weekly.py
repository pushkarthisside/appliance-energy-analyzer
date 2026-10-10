"""Weekly and window statistics for one series (ARCHITECTURE.md §9.1, §7.4)."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.analytics.constants import WEEK_HOURS, WEEK_NAMES, WINDOW_HOURS
from app.nilm.preprocess import (
    block_kwh,
    block_on_stats,
    coverage,
    daily_kwh,
    is_valid_block,
    week_slices,
)


@dataclass(frozen=True)
class WeekStats:
    valid: bool
    coverage: float
    kwh: float | None  # null when the week is invalid
    on_hours: float | None
    avg_on_power_w: float | None


@dataclass(frozen=True)
class SeriesStats:
    kwh_period: float | None
    coverage: float
    weeks: dict[str, WeekStats]
    daily: list[dict] = field(default_factory=list)


def series_stats(values: np.ndarray, start: pd.Timestamp, on_threshold_w: float | None) -> SeriesStats:
    """Weekly kWh / ON-hours / average ON power, window kWh and daily kWh.

    A week statistic is ``None`` if that week is invalid for this series.
    ``on_threshold_w`` may be ``None`` (no ON statistics, e.g. for ``other``).
    """
    weeks: dict[str, WeekStats] = {}
    for name, sl in week_slices().items():
        block = values[sl]
        valid = is_valid_block(block)
        kwh = block_kwh(block, WEEK_HOURS) if valid else None
        on_hours = avg_on = None
        if valid and on_threshold_w is not None:
            on_hours, avg_on = block_on_stats(block, on_threshold_w, WEEK_HOURS)
        weeks[name] = WeekStats(valid, coverage(block), kwh, on_hours, avg_on)
    return SeriesStats(
        kwh_period=block_kwh(values, WINDOW_HOURS),
        coverage=coverage(values),
        weeks=weeks,
        daily=daily_kwh(values, start),
    )


def weekly_kwh(stats: SeriesStats) -> dict[str, float | None]:
    return {name: stats.weeks[name].kwh for name in WEEK_NAMES}
