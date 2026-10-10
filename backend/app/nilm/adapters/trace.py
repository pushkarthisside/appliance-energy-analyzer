"""``trace`` adapter for synthetic demonstration appliances (ARCHITECTURE.md §8.1).

The trace is loaded from the bundle and validated like the aggregate (§6.2). It is
known ground truth for a constructed scenario; it is never a model prediction.
"""

from __future__ import annotations

import numpy as np


class TraceAdapter:
    def __init__(self, appliance_id: str, trace_w: np.ndarray) -> None:
        self.appliance_id = appliance_id
        self._trace = np.asarray(trace_w, dtype="float64")

    def predict(self, mains_w: np.ndarray) -> np.ndarray:
        if mains_w.shape != self._trace.shape:
            raise ValueError("trace length does not match the window")
        return self._trace.copy()
