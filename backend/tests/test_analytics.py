"""TS-U-04…09 — status order, flag boundaries, drivers, savings, ranking, cost (§9)."""

import pytest

from app.analytics.cost import effective_rate, rate_is_unusual, valid_bill_value
from app.analytics.drivers import likely_driver
from app.analytics.flags import evaluate_status, threshold
from app.analytics.rank import rank_key
from app.analytics.savings import savings_kwh_month
from app.analytics.weekly import SeriesStats, WeekStats


def stats(b1, b2, cur, valid=(True, True, True), hours=(10, 10, 10), power=(1000, 1000, 1000)):
    weeks = {}
    for i, name in enumerate(("baseline_1", "baseline_2", "current")):
        kwh = (b1, b2, cur)[i]
        ok = valid[i]
        weeks[name] = WeekStats(
            valid=ok,
            coverage=1.0 if ok else 0.5,
            kwh=kwh if ok else None,
            on_hours=hours[i] if ok else None,
            avg_on_power_w=power[i] if ok else None,
        )
    return SeriesStats(kwh_period=None, coverage=1.0, weeks=weeks)


# ---- worked example from ARCHITECTURE.md §9.5 ----------------------------------------


def test_worked_example():
    flag = evaluate_status(stats(60, 60, 85), energy_uncertainty_pct=15, min_excess_kwh_week=1.0)
    assert flag.threshold == pytest.approx(0.30)  # max(0.25, 2 x 0.15)
    assert flag.status == "unusual"
    assert flag.baseline_kwh == 60 and flag.excess_kwh == 25
    assert flag.change_pct == pytest.approx(41.67, abs=0.01)

    kwh = savings_kwh_month(flag.excess_kwh, 15)
    assert (round(kwh.low, 2), round(kwh.mid, 2), round(kwh.high, 2)) == (91.07, 107.14, 123.21)
    inr = kwh.scaled(effective_rate(4200, 500))  # ₹8.40/kWh
    assert (round(inr.low), round(inr.mid), round(inr.high)) == (765, 900, 1035)


# ---- status order (§9.2) ---------------------------------------------------------------


def test_status_order_first_match_wins():
    current_invalid = evaluate_status(stats(60, 60, 85, valid=(False, True, False)), 15, 1)
    assert (current_invalid.status, current_invalid.status_reason) == ("insufficient_data", "current_week_invalid")

    baseline_invalid = evaluate_status(stats(60, 60, 85, valid=(True, False, True)), 15, 1)
    assert (baseline_invalid.status, baseline_invalid.status_reason) == ("insufficient_data", "baseline_week_invalid")

    tiny = evaluate_status(stats(0.2, 0.4, 5), 15, 1)
    assert (tiny.status, tiny.status_reason) == ("insufficient_data", "baseline_too_small")

    zero = evaluate_status(stats(0, 0, 5), 15, 1)
    assert zero.status == "insufficient_data"


def test_insufficient_data_has_no_change_pct():
    for s in (stats(60, 60, 85, valid=(True, True, False)), stats(0.1, 0.1, 9)):
        flag = evaluate_status(s, 15, 1)
        assert flag.status == "insufficient_data"
        assert flag.change_pct is None and flag.excess_kwh is None


def test_flag_boundaries():
    # exactly baseline x (1 + T) is NOT unusual (strict >)
    assert evaluate_status(stats(60, 60, 78), 15, 1).status == "typical"
    assert evaluate_status(stats(60, 60, 78.01), 15, 1).status == "unusual"
    # excess must be strictly greater than min_excess_kwh_week
    assert evaluate_status(stats(1, 1, 2), 15, 1.0).status == "typical"  # excess 1.0, not > 1.0
    assert evaluate_status(stats(1, 1, 2.01), 15, 1.0).status == "unusual"


def test_threshold_floor_and_error_multiplier():
    assert threshold(5) == pytest.approx(0.25)
    assert threshold(20) == pytest.approx(0.40)


# ---- drivers (§9.4) --------------------------------------------------------------------


def unusual():
    return stats(60, 60, 85)


def test_driver_longer_operating_time():
    s = stats(60, 60, 85, hours=(10, 10, 14), power=(1000, 1000, 1000))
    assert likely_driver(s, "unusual", True) == "longer_operating_time"


def test_driver_higher_power_when_on():
    s = stats(60, 60, 85, hours=(10, 10, 10), power=(1000, 1000, 1400))
    assert likely_driver(s, "unusual", True) == "higher_power_when_on"


def test_driver_unclear_below_min_ratio():
    s = stats(60, 60, 85, hours=(10, 10, 10.5), power=(1000, 1000, 1050))
    assert likely_driver(s, "unusual", True) == "unclear"


def test_driver_null_cases():
    s = stats(60, 60, 85, hours=(10, 10, 14))
    assert likely_driver(s, "typical", True) is None  # only for unusual
    assert likely_driver(s, "unusual", False) is None  # driver_analysis off
    no_on = stats(60, 60, 85, hours=(0, 0, 5))
    assert likely_driver(no_on, "unusual", True) is None  # baseline on-hours not > 0
    missing_power = stats(60, 60, 85, power=(None, 1000, 1000))
    assert likely_driver(missing_power, "unusual", True) is None


# ---- savings, ranking, cost ------------------------------------------------------------


def test_savings_low_never_negative():
    kwh = savings_kwh_month(10, 150)  # e = 1.5 -> mid x (1 - e) < 0
    assert kwh.low == 0.0


def test_ranking_order():
    keys = [
        ("b", rank_key(900, 30, "b")),
        ("a", rank_key(900, 30, "a")),
        ("c", rank_key(900, 45, "c")),
        ("d", rank_key(1200, 10, "d")),
    ]
    assert [name for name, key in sorted(keys, key=lambda x: x[1])] == ["d", "c", "a", "b"]


def test_cost_rules():
    assert effective_rate(4200, 500) == pytest.approx(8.4)
    for bad in (0, -1, float("nan"), float("inf"), 10_000_001):
        assert not valid_bill_value(bad)
        with pytest.raises(ValueError):
            effective_rate(bad, 500)
    assert valid_bill_value(10_000_000)
    assert rate_is_unusual(0.5) and rate_is_unusual(51) and not rate_is_unusual(8.4)
