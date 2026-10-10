"""Registry loading and validation (ARCHITECTURE.md §5).

``registry.json`` defines every appliance the system may run. A broken file is fatal
(``RegistryError``); an individual invalid entry is reported in ``entry_errors`` and
never runs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.analytics.constants import OTHER_ID

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,31}$")

VALID_COMBINATIONS = {
    ("real_model", "candidate", "onnx_seq2point"),
    ("real_model", "go", "onnx_seq2point"),
    ("real_model", "no_go", "onnx_seq2point"),
    ("synthetic_trace", "demo", "trace"),
}


class RegistryError(ValueError):
    """The registry file as a whole is unusable (startup is ``not_ready``)."""


@dataclass(frozen=True)
class RegistryEntry:
    id: str
    name: str
    appliance_class: str
    provenance: str  # real_model | synthetic_trace
    status: str  # candidate | go | no_go | demo
    adapter: str  # onnx_seq2point | trace
    model: dict | None
    on_threshold_w: float | None
    driver_analysis: bool
    weather_sensitive: bool
    energy_uncertainty_pct: float | None
    uncertainty_source: str | None
    min_excess_kwh_week: float | None
    action_id: str
    evaluation_ref: str | None

    @property
    def runnable(self) -> bool:
        """``go`` real models and ``demo`` synthetic traces run; nothing else does."""
        return self.status in ("go", "demo")


@dataclass
class Registry:
    registry_version: int
    interval_seconds: int
    entries: dict[str, RegistryEntry] = field(default_factory=dict)
    entry_errors: dict[str, str] = field(default_factory=dict)

    def runnable(self) -> dict[str, RegistryEntry]:
        return {k: v for k, v in self.entries.items() if v.runnable}


def _entry_problem(raw: dict[str, Any]) -> str | None:
    combo = (raw.get("provenance"), raw.get("status"), raw.get("adapter"))
    if combo not in VALID_COMBINATIONS:
        return f"invalid provenance/status/adapter combination {combo}"
    if raw.get("provenance") == "synthetic_trace" and raw.get("model") is not None:
        return "synthetic_trace entries must have model null"
    if raw.get("status") in ("go", "demo"):
        for key in ("energy_uncertainty_pct", "min_excess_kwh_week"):
            if raw.get(key) is None:
                return f"{key} is null"
        if raw.get("driver_analysis") and raw.get("on_threshold_w") is None:
            return "on_threshold_w is null while driver_analysis is true"
    if raw.get("status") == "go":
        model = raw.get("model") or {}
        norm = model.get("norm") or {}
        if not model.get("path") or any(norm.get(k) is None for k in ("mains_mean", "mains_std", "app_mean", "app_std")):
            return "go entry has incomplete model/norm fields"
    return None


def parse_registry(data: dict[str, Any]) -> Registry:
    if not isinstance(data, dict) or not isinstance(data.get("appliances"), list):
        raise RegistryError("registry must be an object with an 'appliances' list")
    if data.get("interval_seconds") != 60:
        raise RegistryError("interval_seconds must be 60")
    if not isinstance(data.get("registry_version"), int):
        raise RegistryError("registry_version must be an integer")

    registry = Registry(data["registry_version"], data["interval_seconds"])
    for raw in data["appliances"]:
        app_id = raw.get("id") if isinstance(raw, dict) else None
        if not isinstance(app_id, str) or not ID_PATTERN.match(app_id) or app_id == OTHER_ID:
            raise RegistryError(f"invalid appliance id {app_id!r}")
        if app_id in registry.entries or app_id in registry.entry_errors:
            raise RegistryError(f"duplicate appliance id {app_id!r}")
        problem = _entry_problem(raw)
        if problem:
            registry.entry_errors[app_id] = problem
            continue
        entry = RegistryEntry(
            id=app_id,
            name=str(raw.get("name") or app_id),
            appliance_class=str(raw.get("class") or app_id),
            provenance=raw["provenance"],
            status=raw["status"],
            adapter=raw["adapter"],
            model=raw.get("model"),
            on_threshold_w=raw.get("on_threshold_w"),
            driver_analysis=bool(raw.get("driver_analysis", False)),
            weather_sensitive=bool(raw.get("weather_sensitive", False)),
            energy_uncertainty_pct=raw.get("energy_uncertainty_pct"),
            uncertainty_source=raw.get("uncertainty_source"),
            min_excess_kwh_week=raw.get("min_excess_kwh_week"),
            action_id=str(raw.get("action_id") or ""),
            evaluation_ref=raw.get("evaluation_ref"),
        )
        registry.entries[app_id] = entry
    return registry


def load_registry(path: str | Path) -> Registry:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"cannot read registry: {exc}") from exc
    return parse_registry(data)
