"""Cost attribution from the bill (ARCHITECTURE.md §9.7).

The effective rate spreads fixed charges and slabs over all units, so it is an average,
not the marginal cost. Cost figures are estimates for the 21-day window, not the bill.
"""

from __future__ import annotations

import math

MAX_BILL_VALUE = 10_000_000
RATE_WARNING_LOW = 1.0
RATE_WARNING_HIGH = 50.0


def valid_bill_value(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and 0 < value <= MAX_BILL_VALUE


def effective_rate(bill_amount_inr: float, bill_units_kwh: float) -> float:
    if not (valid_bill_value(bill_amount_inr) and valid_bill_value(bill_units_kwh)):
        raise ValueError("invalid_bill")
    return bill_amount_inr / bill_units_kwh


def rate_is_unusual(rate: float) -> bool:
    """A rate below ₹1 or above ₹50 per kWh adds the ``bill_rate_unusual`` warning."""
    return rate < RATE_WARNING_LOW or rate > RATE_WARNING_HIGH


def cost_inr(kwh: float | None, rate: float) -> float | None:
    return None if kwh is None else kwh * rate
