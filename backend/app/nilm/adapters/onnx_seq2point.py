"""``onnx_seq2point`` adapter: real-model inference (ARCHITECTURE.md §8.1).

Sequence-to-point: the model sees a 99-minute window of the aggregate signal centred on a
minute and predicts the appliance's power at that centre minute.

- Input windows are normalized with the registry's training-only stats:
  ``(x - mains_mean) / mains_std``; output is de-normalized: ``y * app_std + app_mean``.
- A minute's estimate is NaN if its window contains any NaN or extends beyond the series
  (the first/last ``window // 2`` minutes). No imputation.
- ONNX Runtime CPU provider, batch size 2048.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

BATCH_SIZE = 2048


class OnnxSeq2PointAdapter:
    def __init__(self, session, window: int, norm: dict[str, float]) -> None:
        if window % 2 != 1:
            raise ValueError("window must be odd so it has a centre minute")
        for key in ("mains_mean", "mains_std", "app_mean", "app_std"):
            if norm.get(key) is None:
                raise ValueError(f"norm.{key} is required")
        if norm["mains_std"] <= 0 or norm["app_std"] <= 0:
            raise ValueError("normalization std values must be > 0")
        self.session = session
        self.window = window
        self.norm = norm
        self.input_name = session.get_inputs()[0].name

    @classmethod
    def from_file(cls, model_path: str | Path, window: int, norm: dict[str, float]) -> "OnnxSeq2PointAdapter":
        import onnxruntime as ort

        path = Path(model_path)
        if not path.is_file():
            raise FileNotFoundError(f"model file not found: {path}")
        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        return cls(session, window, norm)

    @classmethod
    def from_registry_entry(cls, entry, artifact_root: str | Path) -> "OnnxSeq2PointAdapter":
        model = entry.model or {}
        return cls.from_file(Path(artifact_root) / model["path"], int(model["window_minutes"]), model["norm"])

    def predict(self, mains_w: np.ndarray) -> np.ndarray:
        mains = np.asarray(mains_w, dtype="float64")
        n, w, half = mains.size, self.window, self.window // 2
        out = np.full(n, np.nan)
        if n < w:
            return out
        windows = np.lib.stride_tricks.sliding_window_view(mains, w)  # row i is centred on minute i + half
        complete = ~np.isnan(windows).any(axis=1)
        rows = np.flatnonzero(complete)
        if rows.size == 0:
            return out
        scale = (windows[rows] - self.norm["mains_mean"]) / self.norm["mains_std"]
        scale = scale.astype(np.float32)
        preds = np.empty(rows.size, dtype="float64")
        for start in range(0, rows.size, BATCH_SIZE):
            batch = scale[start : start + BATCH_SIZE]
            result = self.session.run(None, {self.input_name: batch})[0]
            preds[start : start + batch.shape[0]] = np.asarray(result, dtype="float64").reshape(-1)
        out[rows + half] = preds * self.norm["app_std"] + self.norm["app_mean"]
        return out
