"""Issue ranking (ARCHITECTURE.md §9.6)."""

from __future__ import annotations

from typing import Iterable, TypeVar

T = TypeVar("T")


def rank_key(inr_mid: float, change_pct: float, appliance_id: str) -> tuple:
    """Sort by ₹ mid descending, then change % descending, then appliance id ascending."""
    return (-inr_mid, -change_pct, appliance_id)


def ranked(items: Iterable[T], key) -> list[T]:
    return sorted(items, key=key)
