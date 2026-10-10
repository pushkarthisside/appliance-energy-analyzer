"""Randomized simulated households for the synthetic-data prototype model.

Each household has an air conditioner (the target) plus distractor loads that make
disaggregation non-trivial: a water heater, a cycling fridge, short kitchen spikes, and a
background load with an evening bump. Everything is generated from a seed and is
constructed data, not a measurement. Seeds here never overlap the demo scenario.
"""

from __future__ import annotations

import numpy as np

MINUTES_PER_DAY = 1440


def _cycle(n: int, on: int, off: int, phase: int) -> np.ndarray:
    period = on + off
    return ((np.arange(n) + phase) % period) < on


def household(seed: int, days: int = 21) -> tuple[np.ndarray, np.ndarray]:
    """Return (aggregate_w, air_conditioner_w), both float64[days * 1440]."""
    rng = np.random.Generator(np.random.PCG64(seed))
    n = days * MINUTES_PER_DAY
    minute = np.arange(n) % MINUTES_PER_DAY

    # Air conditioner: 1-3 sessions per day with compressor cycling inside each session.
    ac_power = rng.uniform(1000, 1800)
    ac = np.zeros(n)
    for day in range(days):
        for _ in range(rng.integers(1, 4)):
            start = day * MINUTES_PER_DAY + int(rng.choice([rng.integers(720, 1020), rng.integers(1260, 1380)]))
            length = int(rng.integers(60, 300))
            end = min(start + length, (day + 1) * MINUTES_PER_DAY)
            span = end - start
            cycling = _cycle(span, int(rng.integers(12, 25)), int(rng.integers(4, 10)), int(rng.integers(0, 30)))
            ac[start:end] = np.where(cycling, ac_power * rng.normal(1.0, 0.04, span), ac[start:end])

    # Water heater: morning and evening bursts.
    heater = np.zeros(n)
    heater_power = rng.uniform(1800, 2500)
    for day in range(days):
        for centre in (rng.integers(360, 480), rng.integers(1140, 1260)):
            start = day * MINUTES_PER_DAY + int(centre)
            heater[start : start + int(rng.integers(15, 45))] = heater_power

    # Fridge: continuous cycling.
    fridge = np.where(_cycle(n, int(rng.integers(15, 25)), int(rng.integers(20, 35)), int(rng.integers(0, 60))),
                      rng.uniform(90, 180), 3.0)

    # Kitchen spikes (kettle / microwave): a few short high-power events per day.
    kitchen = np.zeros(n)
    for day in range(days):
        for _ in range(rng.integers(2, 6)):
            start = day * MINUTES_PER_DAY + int(rng.integers(360, 1380))
            kitchen[start : start + int(rng.integers(2, 6))] = rng.uniform(900, 1600)

    base = rng.uniform(150, 400)
    background = base + np.where((minute >= 1110) & (minute < 1380), rng.uniform(150, 400), 0.0)
    noise = rng.normal(0.0, 20.0, n)

    aggregate = np.clip(ac + heater + fridge + kitchen + background + noise, 0.0, None)
    return np.round(aggregate, 1), np.round(ac, 1)
