"""TS-U-01/03 — minute grid, invalid values, no imputation, week validity, scaling (§7)."""

import numpy as np
import pandas as pd
import pytest

from app.analytics.constants import WEEK_MINUTES
from app.nilm.preprocess import (
    LOCAL_TZ,
    block_kwh,
    block_on_stats,
    clean_power,
    daily_kwh,
    is_valid_block,
    to_minute_grid,
    window_start,
)

START = pd.Timestamp("2026-01-05T00:00:00", tz=LOCAL_TZ)


def frame(rows):
    return pd.DataFrame(rows, columns=["timestamp", "power_w"])


def test_resamples_to_one_minute_means_and_leaves_empty_bins_missing():
    series = clean_power(
        frame(
            [
                ["2026-01-05T00:00:10+05:30", 100],
                ["2026-01-05T00:00:40+05:30", 200],  # same minute -> mean 150
                ["2026-01-05T00:03:00+05:30", 400],  # minutes 1 and 2 have no reading
            ]
        )
    )
    grid = to_minute_grid(series, START, 5)
    assert grid[0] == pytest.approx(150.0)
    assert np.isnan(grid[1]) and np.isnan(grid[2])  # no interpolation, no imputation
    assert grid[3] == pytest.approx(400.0)
    assert np.isnan(grid[4])


def test_invalid_values_become_missing():
    series = clean_power(
        frame(
            [
                ["2026-01-05T00:00:00+05:30", -5],
                ["2026-01-05T00:01:00+05:30", 30_001],
                ["2026-01-05T00:02:00+05:30", "abc"],
                ["2026-01-05T00:03:00+05:30", 30_000],
            ]
        )
    )
    grid = to_minute_grid(series, START, 4)
    assert np.isnan(grid[:3]).all()
    assert grid[3] == 30_000


def test_duplicate_timestamps_are_averaged():
    series = clean_power(frame([["2026-01-05T00:00:00+05:30", 100], ["2026-01-05T00:00:00+05:30", 300]]))
    assert to_minute_grid(series, START, 1)[0] == pytest.approx(200.0)


def test_naive_timestamps_are_local_time_and_utc_is_converted():
    naive = clean_power(frame([["2026-01-05T00:00:00", 100]]))
    utc = clean_power(frame([["2026-01-04T18:30:00+00:00", 100]]))  # = 00:00 IST
    assert to_minute_grid(naive, START, 1)[0] == 100
    assert to_minute_grid(utc, START, 1)[0] == 100


def test_window_start_must_be_local_midnight():
    assert window_start("2026-04-06T00:00:00+05:30") == pd.Timestamp("2026-04-06", tz=LOCAL_TZ)
    with pytest.raises(ValueError):
        window_start("2026-04-06T00:01:00+05:30")


def test_week_validity_boundary_is_80_percent():
    week = np.full(WEEK_MINUTES, 100.0)
    valid_minutes = int(WEEK_MINUTES * 0.8)  # 8 064
    exactly = week.copy()
    exactly[valid_minutes:] = np.nan
    below = week.copy()
    below[valid_minutes - 1 :] = np.nan
    assert is_valid_block(exactly)
    assert not is_valid_block(below)


def test_energy_scales_for_missing_minutes():
    week = np.full(WEEK_MINUTES, 1000.0)
    assert block_kwh(week, 168) == pytest.approx(168.0)  # 1 kW for 168 h
    week[: int(WEEK_MINUTES * 0.15)] = np.nan  # 15 % missing -> mean of valid minutes, scaled
    assert block_kwh(week, 168) == pytest.approx(168.0)
    assert block_kwh(np.full(10, np.nan), 168) is None


def test_on_statistics():
    values = np.array([0.0, 0.0, 1000.0, 1200.0, np.nan])  # 2 of 4 valid minutes ON
    on_hours, avg_on = block_on_stats(values, 150.0, 168)
    assert on_hours == pytest.approx(84.0)
    assert avg_on == pytest.approx(1100.0)
    assert block_on_stats(np.zeros(4), 150.0, 168) == (0.0, None)


def test_daily_kwh_is_null_below_half_coverage():
    two_days = np.full(2 * 1440, 1000.0)
    two_days[1440 : 1440 + 721] = np.nan  # day 2 has < 50 % valid minutes
    days = daily_kwh(two_days, START)
    assert days[0] == {"date": "2026-01-05", "kwh": pytest.approx(24.0)}
    assert days[1]["kwh"] is None
