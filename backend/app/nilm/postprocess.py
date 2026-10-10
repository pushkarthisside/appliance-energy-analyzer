"""Postprocessing of real-model estimates (ARCHITECTURE.md §8.3).

Identical in ``ml/evaluate.py`` and serving. Synthetic traces are not touched here:
they are known exactly and are added back for display.
"""

from __future__ import annotations

import numpy as np


def postprocess(
    mains_for_models: np.ndarray, estimates: dict[str, np.ndarray]
) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Clip, scale and compute ``other``.

    Per minute where ``mains_for_models`` is valid:
    1. clip each estimate to ``[0, mains]`` (a NaN estimate counts as 0 in the sum but
       stays NaN for that appliance's own statistics);
    2. if the sum exceeds ``mains``, scale all estimates by ``mains / sum``;
    3. ``other = mains − Σ estimates`` (≥ 0 by construction).
    Minutes where ``mains`` is missing are missing for everything.
    """
    mains = np.asarray(mains_for_models, dtype="float64")
    valid = ~np.isnan(mains)
    names = list(estimates)
    if not names:
        return {}, mains.copy()

    stack = np.vstack([np.asarray(estimates[n], dtype="float64") for n in names])
    own_missing = np.isnan(stack)
    clipped = np.clip(np.nan_to_num(stack, nan=0.0), 0.0, None)
    clipped = np.minimum(clipped, np.where(valid, mains, 0.0))

    total = clipped.sum(axis=0)
    over = valid & (total > mains)
    with np.errstate(divide="ignore", invalid="ignore"):
        factor = np.where(over, mains / total, 1.0)
    scaled = clipped * factor

    other = np.where(valid, np.maximum(mains - scaled.sum(axis=0), 0.0), np.nan)
    result = {}
    for i, name in enumerate(names):
        series = scaled[i].copy()
        series[own_missing[i] | ~valid] = np.nan
        result[name] = series
    return result, other
