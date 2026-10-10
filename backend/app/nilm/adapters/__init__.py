"""Estimation adapters (ARCHITECTURE.md §8.1).

Contract: ``predict(mains_w: float64[T] with NaN) -> float64[T] with NaN``.

- ``trace``: returns a bundle's known synthetic trace; no inference.
- ``onnx_seq2point``: real-model inference. Not implemented yet; it is only needed once
  a real model receives ``go`` under the frozen criteria.
"""
