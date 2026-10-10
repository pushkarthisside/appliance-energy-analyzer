"""Startup state: everything loaded once and kept in memory (ARCHITECTURE.md §15.1-§15.3).

1. sync/validate artifacts (``storage``)
2. load registry, actions, optional emissions and evaluation
3. load adapters for ``go`` real models (``demo`` traces need no load)
4. precompute every sample with ``run_pipeline`` (bill-independent) and cache it
5. ready = valid registry and at least one sample ready
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Settings
from app.ingest.bundle import SAMPLE_IDS, BundleError, load_bundle
from app.nilm.registry import Registry, RegistryError, load_registry
from app.pipeline import PipelineResult, run_pipeline
from app.storage import SyncResult, sync_artifacts

log = logging.getLogger("aea.runtime")


@dataclass
class SampleState:
    id: str
    state: str  # ready | failed
    detail: str | None
    result: PipelineResult | None = None


@dataclass
class Runtime:
    settings: Settings
    sync: SyncResult
    registry: Registry | None = None
    registry_error: str | None = None
    actions: dict | None = None
    emissions: dict | None = None
    evaluation: dict | None = None
    adapter_failures: dict[str, str] = field(default_factory=dict)
    samples: dict[str, SampleState] = field(default_factory=dict)

    @property
    def evidence_level(self) -> str:
        return (self.evaluation or {}).get("evidence_level") or "none"

    @property
    def ready(self) -> bool:
        return self.registry is not None and any(s.state == "ready" for s in self.samples.values())

    @property
    def status(self) -> str:
        if not self.ready:
            return "not_ready"
        degraded = (
            self.adapter_failures
            or any(s.state == "failed" for s in self.samples.values())
            or self.sync.state == "failed_using_cache"
        )
        return "degraded" if degraded else "ok"


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def load_real_adapters(registry: Registry, root: Path) -> tuple[dict, dict[str, str]]:
    """Create an inference session for each ``go`` real model. Failures are recorded and
    that appliance is excluded (its energy then falls into ``other``)."""
    adapters, failures = {}, {}
    for entry in registry.runnable().values():
        if entry.provenance != "real_model":
            continue
        try:
            from app.nilm.adapters.onnx_seq2point import OnnxSeq2PointAdapter

            adapters[entry.id] = OnnxSeq2PointAdapter.from_registry_entry(entry, root)
        except Exception as exc:  # missing file, missing onnxruntime, bad model
            failures[entry.id] = f"model load failed: {exc}"
            log.error("could not load %s: %s", entry.id, exc)
    return adapters, failures


def build_runtime(settings: Settings, s3_client=None) -> Runtime:
    sync = sync_artifacts(settings, s3_client)
    runtime = Runtime(settings=settings, sync=sync)
    if sync.root is None:
        runtime.registry_error = sync.detail
        return runtime
    root = sync.root

    try:
        runtime.registry = load_registry(root / "registry.json")
    except RegistryError as exc:
        runtime.registry_error = str(exc)
        return runtime
    runtime.actions = _read_json(root / "config" / "actions.json")
    runtime.emissions = _read_json(root / "config" / "emissions.json")  # optional; validated in apply_bill
    runtime.evaluation = _read_json(root / "evaluation" / "evaluation.json")

    adapters, runtime.adapter_failures = load_real_adapters(runtime.registry, root)

    samples_dir = root / "samples"
    for sample_id in SAMPLE_IDS:
        sample_dir = samples_dir / sample_id
        if not (sample_dir / "manifest.json").is_file():
            continue  # not built (e.g. typical_period without a go model): not offered
        try:
            bundle = load_bundle(sample_dir)
            result = run_pipeline(bundle, runtime.registry, runtime.evidence_level, adapters)
            if not result.appliances:
                raise BundleError("no monitored appliance in this sample")
            runtime.samples[sample_id] = SampleState(sample_id, "ready", None, result)
        except Exception as exc:  # one bad sample must not stop the others
            log.error("sample %s failed: %s", sample_id, exc)
            runtime.samples[sample_id] = SampleState(sample_id, "failed", str(exc))
    return runtime
