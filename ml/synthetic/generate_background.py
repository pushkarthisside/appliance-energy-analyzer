"""Deterministic synthetic background load for the fully synthetic fallback (§10.2-§10.3).

The background represents unitemized household load. It is not an appliance, is never
registered, and is never included in appliance metrics. Real-model inference never runs
on a fully synthetic aggregate.
"""

from __future__ import annotations

import numpy as np

from app.analytics.constants import MINUTES_PER_DAY
from synthetic.generate import on_mask_for_day


def generate_background(background: dict, days: int) -> np.ndarray:
    rng = np.random.Generator(np.random.PCG64(int(background["seed"])))
    noise = rng.normal(0.0, float(background["noise_std_w"]), size=days * MINUTES_PER_DAY)
    day_profile = np.full(MINUTES_PER_DAY, float(background["base_w"]))
    for block in background.get("daily_blocks", []):
        mask = on_mask_for_day([{"start": block["start"], "duration_minutes": block["duration_minutes"]}])
        day_profile[mask] += float(block["power_w"])
    values = np.tile(day_profile, days) + noise
    return np.round(np.clip(values, 0.0, None), 1)
