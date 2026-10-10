"""Analysis pipeline (ARCHITECTURE.md §8.2, §9, §11.5, §15.1-§15.2).

Two functions form the interface used by the API layer:

1. ``run_pipeline(bundle, registry, evidence_level)`` -> ``PipelineResult``
   Bill-independent. Run once per sample at startup and keep the result in memory.
2. ``apply_bill(result, bill_amount_inr, bill_units_kwh, actions, ...)`` -> ``AnalysisResponse``
   Per request: cost, savings in ₹, issues and ranking. Fast (no signal processing).

Provenance rules enforced here:
- synthetic traces run only when listed in the bundle and registered with status ``demo``;
- real models run only with status ``go`` and never on a fully synthetic bundle;
- ``other`` is never flagged and never gets a driver or savings;
- synthetic outputs always produce illustrative savings and never emissions numbers.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

import numpy as np
import pandas as pd

from app.analytics import cost as cost_rules
from app.analytics.constants import (
    OTHER_ID,
    SIGNAL_STEP_MINUTES,
    WEEK_MINUTES,
    WEEK_NAMES,
    WINDOW_DAYS,
)
from app.analytics.drivers import likely_driver
from app.analytics.flags import FlagResult, evaluate_status
from app.analytics.rank import rank_key
from app.analytics.savings import savings_kwh_month
from app.analytics.weekly import SeriesStats, series_stats, weekly_kwh
from app.analytics.wording import assert_clean
from app.ingest.bundle import Bundle
from app.nilm.adapters.trace import TraceAdapter
from app.nilm.postprocess import postprocess
from app.nilm.preprocess import week_slices
from app.nilm.registry import Registry, RegistryEntry
from app.schemas import AnalysisResponse


class Adapter(Protocol):
    def predict(self, mains_w: np.ndarray) -> np.ndarray: ...


class PipelineError(RuntimeError):
    """The bundle cannot be analysed (the sample is reported as failed)."""


@dataclass(frozen=True)
class ApplianceAnalysis:
    entry: RegistryEntry
    stats: SeriesStats
    flag: FlagResult
    driver: str | None


@dataclass(frozen=True)
class PipelineResult:
    """Bill-independent result for one sample, cached in memory at startup."""

    sample_id: str
    title: str
    description: str
    simulated: bool
    simulated_appliance_ids: list[str]
    evidence_level: str | None
    start: pd.Timestamp
    total: SeriesStats
    appliances: list[ApplianceAnalysis]
    other: SeriesStats
    signals: dict
    unavailable: list[tuple[str, str]] = field(default_factory=list)  # (appliance id, reason)


# ---------------------------------------------------------------------------
# 1. Bill-independent pipeline
# ---------------------------------------------------------------------------


def _signals(start: pd.Timestamp, aggregate: np.ndarray, series: dict[str, np.ndarray]) -> dict:
    """Current week at 15-minute means (672 points); ``None`` where a bin has no valid minute."""
    current = week_slices()["current"]

    def downsample(values: np.ndarray) -> list[float | None]:
        bins = values[current].reshape(-1, SIGNAL_STEP_MINUTES)
        out: list[float | None] = []
        for row in bins:
            valid = row[~np.isnan(row)]
            out.append(round(float(valid.mean()), 1) if valid.size else None)
        return out

    return {
        "window": "current_week",
        "start": (start + pd.Timedelta(minutes=2 * WEEK_MINUTES)).isoformat(),
        "step_minutes": SIGNAL_STEP_MINUTES,
        "aggregate_w": downsample(aggregate),
        "by_appliance": {name: downsample(values) for name, values in series.items()},
    }


def run_pipeline(
    bundle: Bundle,
    registry: Registry,
    evidence_level: str | None = None,
    real_adapters: dict[str, Adapter] | None = None,
) -> PipelineResult:
    """load bundle → grid → Σ synthetic traces → models on the real part → postprocess → stats.

    ``real_adapters`` maps ``go`` real-model ids to loaded adapters (empty until a real
    model passes evaluation). ``evidence_level`` comes from ``evaluation.json``.
    """
    real_adapters = real_adapters or {}
    aggregate = np.asarray(bundle.aggregate_w, dtype="float64")
    missing = np.isnan(aggregate)
    unavailable: list[tuple[str, str]] = []
    runnable = registry.runnable()

    # Synthetic demonstration appliances: known traces, only if listed AND registered as demo.
    synthetic: dict[str, np.ndarray] = {}
    for app_id in bundle.synthetic_ids:
        entry = runnable.get(app_id)
        if entry is None or entry.provenance != "synthetic_trace":
            reason = registry.entry_errors.get(app_id, "not registered as a demo synthetic trace")
            unavailable.append((app_id, reason))
            continue
        trace = TraceAdapter(app_id, bundle.traces[app_id]).predict(aggregate)
        trace[missing] = np.nan  # minutes missing in the aggregate are missing for everything
        synthetic[app_id] = trace

    synthetic_sum = np.zeros_like(aggregate)
    for trace in synthetic.values():
        synthetic_sum += np.nan_to_num(trace, nan=0.0)
    mains_for_models = np.where(missing, np.nan, np.maximum(aggregate - synthetic_sum, 0.0)) if synthetic else aggregate.copy()

    # Real models: status go only, and NEVER invoked on a fully synthetic aggregate (§15.4).
    # Callers may pass the same loaded adapters for every sample; for a fully synthetic
    # bundle they are simply not run (not an error, and not an "unavailable" warning).
    estimates: dict[str, np.ndarray] = {}
    go_entries = [e for e in runnable.values() if e.provenance == "real_model"]
    if not bundle.fully_synthetic:
        for entry in go_entries:
            adapter = real_adapters.get(entry.id)
            if adapter is None:
                unavailable.append((entry.id, "model not loaded"))
                continue
            estimates[entry.id] = adapter.predict(mains_for_models)
    real_estimates, other = postprocess(mains_for_models, estimates)

    displayed = np.where(missing, np.nan, mains_for_models + synthetic_sum)
    analyses: list[ApplianceAnalysis] = []
    series_for_signals: dict[str, np.ndarray] = {}
    order = [e.id for e in registry.entries.values()]
    monitored = {**real_estimates, **synthetic}
    for app_id in sorted(monitored, key=order.index):
        entry = registry.entries[app_id]
        values = monitored[app_id]
        stats = series_stats(values, bundle.start, entry.on_threshold_w)
        flag = evaluate_status(stats, entry.energy_uncertainty_pct, entry.min_excess_kwh_week)
        driver = likely_driver(stats, flag.status, entry.driver_analysis)
        analyses.append(ApplianceAnalysis(entry, stats, flag, driver))
        series_for_signals[app_id] = values
    series_for_signals[OTHER_ID] = other

    manifest = bundle.manifest
    return PipelineResult(
        sample_id=bundle.sample_id,
        title=manifest.get("title", bundle.sample_id),
        description=manifest.get("description", ""),
        simulated=bool(manifest.get("simulated")),
        simulated_appliance_ids=[a for a in bundle.synthetic_ids if a in synthetic],
        evidence_level=evidence_level,
        start=bundle.start,
        total=series_stats(displayed, bundle.start, None),
        appliances=analyses,
        other=series_stats(other, bundle.start, None),
        signals=_signals(bundle.start, displayed, series_for_signals),
        unavailable=unavailable,
    )


# ---------------------------------------------------------------------------
# 2. Per-request: apply the bill
# ---------------------------------------------------------------------------

EMISSIONS_FIELDS = (
    "factor_kg_co2e_per_kwh",
    "source_name",
    "source_url",
    "edition",
    "publication_year",
    "geography",
    "retrieved_on",
    "verified_by",
)


def complete_emissions(emissions: dict | None) -> dict | None:
    """§6.5: all fields required and factor > 0, otherwise treated as absent."""
    if not emissions or any(emissions.get(k) in (None, "") for k in EMISSIONS_FIELDS):
        return None
    factor = emissions["factor_kg_co2e_per_kwh"]
    if not isinstance(factor, (int, float)) or factor <= 0:
        return None
    return {k: emissions[k] for k in EMISSIONS_FIELDS}


def _r2(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def _r1(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def _inr(value: float | None) -> float | None:
    return None if value is None else float(round(value))


def _share(kwh: float | None, total: float | None) -> float | None:
    if kwh is None or not total:
        return None
    return round(kwh / total * 100.0, 2)


def _appliance_row(app: ApplianceAnalysis, rate: float, total_kwh: float | None) -> dict:
    stats = app.stats
    return {
        "id": app.entry.id,
        "name": app.entry.name,
        "provenance": app.entry.provenance,
        "kwh_period": _r2(stats.kwh_period),
        "cost_period_inr": _inr(cost_rules.cost_inr(stats.kwh_period, rate)),
        "share_pct": _share(stats.kwh_period, total_kwh),
        "coverage_pct": round(stats.coverage * 100.0, 1),
        "weekly_kwh": {k: _r2(v) for k, v in weekly_kwh(stats).items()},
        "status": app.flag.status,
        "status_reason": app.flag.status_reason,
        "daily_kwh": [{"date": d["date"], "kwh": _r2(d["kwh"])} for d in stats.daily],
    }


def _issue(app: ApplianceAnalysis, rate: float, actions: dict, emissions: dict | None) -> dict:
    flag = app.flag
    entry = app.entry
    basis = "synthetic_trace" if entry.provenance == "synthetic_trace" else "real_model"
    illustrative = basis != "real_model"
    kwh = savings_kwh_month(flag.excess_kwh, entry.energy_uncertainty_pct)
    inr = kwh.scaled(rate)
    kg = None
    if emissions is not None and not illustrative:
        co2 = kwh.scaled(float(emissions["factor_kg_co2e_per_kwh"]))
        kg = {"low": round(co2.low, 2), "mid": round(co2.mid, 2), "high": round(co2.high, 2)}

    caveats = [actions["caveats"]["general"]]
    if entry.weather_sensitive:
        caveats.append(actions["caveats"]["weather_sensitive"])
    driver_text = actions["driver_texts"][app.driver] if app.driver else None
    action_text = actions["actions"][entry.action_id]
    for text in [*caveats, driver_text or "", action_text, actions["savings_label"]]:
        assert_clean(text)

    return {
        "appliance_id": entry.id,
        "appliance_name": entry.name,
        "basis": basis,
        "current_kwh": round(flag.current_kwh, 2),
        "baseline_kwh": round(flag.baseline_kwh, 2),
        "excess_kwh_week": round(flag.excess_kwh, 2),
        "change_pct": round(flag.change_pct, 1),
        "threshold_pct": round(flag.threshold * 100.0, 1),
        "driver": app.driver,
        "driver_text": driver_text,
        "caveats": caveats,
        "recommendation": {"action_id": entry.action_id, "text": action_text},
        "savings": {
            "label": actions["savings_label"],
            "illustrative": illustrative,
            "kwh_per_month": {"low": round(kwh.low, 2), "mid": round(kwh.mid, 2), "high": round(kwh.high, 2)},
            "inr_per_month": {"low": float(round(inr.low)), "mid": float(round(inr.mid)), "high": float(round(inr.high))},
            "kg_co2e_per_month": kg,
        },
        "_sort": rank_key(inr.mid, flag.change_pct, entry.id),  # unrounded values decide order
    }


def apply_bill(
    result: PipelineResult,
    bill_amount_inr: float,
    bill_units_kwh: float,
    actions: dict,
    emissions: dict | None = None,
    alert_status: str | None = None,
) -> AnalysisResponse:
    """Turn a cached ``PipelineResult`` plus a bill into the API response (§11.5).

    Raises ``ValueError("invalid_bill")`` for an invalid bill (the API maps it to 422).
    ``alert_status`` is set by the caller after publishing (``sent``/``failed``/
    ``disabled``/``cooldown``); when omitted it is ``no_issues`` or ``disabled``.
    """
    rate = cost_rules.effective_rate(bill_amount_inr, bill_units_kwh)
    emissions = complete_emissions(emissions)
    total_kwh = result.total.kwh_period

    warnings = []
    if cost_rules.rate_is_unusual(rate):
        warnings.append(
            {
                "code": "bill_rate_unusual",
                "message": f"The effective rate of ₹{rate:.2f}/kWh is unusual; please check the bill amount and units.",
            }
        )
    for app_id, _reason in result.unavailable:
        warnings.append(
            {
                "code": "appliance_unavailable",
                "message": f"{app_id} could not be analysed; its energy is included in Other (not itemized).",
            }
        )

    rows = [_appliance_row(a, rate, total_kwh) for a in result.appliances]
    rows.append(
        {
            "id": OTHER_ID,
            "name": "Other",
            "provenance": "residual",
            "kwh_period": _r2(result.other.kwh_period),
            "cost_period_inr": _inr(cost_rules.cost_inr(result.other.kwh_period, rate)),
            "share_pct": _share(result.other.kwh_period, total_kwh),
            "coverage_pct": round(result.other.coverage * 100.0, 1),
            "weekly_kwh": {k: _r2(v) for k, v in weekly_kwh(result.other).items()},
            "status": None,
            "status_reason": None,
            "daily_kwh": [],
        }
    )

    issues = [
        _issue(a, rate, actions, emissions)
        for a in result.appliances
        if a.flag.status == "unusual"
    ]
    issues.sort(key=lambda i: i.pop("_sort"))
    for rank, issue in enumerate(issues, start=1):
        issue["rank"] = rank

    measured = [a for a in result.appliances if a.stats.kwh_period is not None]
    largest = (
        sorted(measured, key=lambda a: (-a.stats.kwh_period, a.entry.id))[0].entry.id if measured else None
    )

    start = result.start
    weeks = {}
    for i, name in enumerate(WEEK_NAMES):
        week = result.total.weeks[name]
        weeks[name] = {
            "start": (start + pd.Timedelta(days=7 * i)).isoformat(),
            "end": (start + pd.Timedelta(days=7 * (i + 1))).isoformat(),
            "valid": week.valid,
            "coverage_pct": round(week.coverage * 100.0, 1),
        }

    if alert_status is None:
        alert_status = "disabled" if issues else "no_issues"

    response = {
        "analysis_id": f"an_{uuid.uuid4().hex[:8]}",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {
            "kind": "sample",
            "sample_id": result.sample_id,
            "title": result.title,
            "description": result.description,
            "simulated": result.simulated,
            "simulated_appliance_ids": result.simulated_appliance_ids,
            "evidence_level": result.evidence_level,
            "validated_domain": True,
        },
        "period": {
            "start": start.isoformat(),
            "end": (start + pd.Timedelta(days=WINDOW_DAYS)).isoformat(),
            "days": WINDOW_DAYS,
            "coverage_pct": round(result.total.coverage * 100.0, 1),
            "weeks": weeks,
        },
        "cost": {
            "bill_amount_inr": bill_amount_inr,
            "bill_units_kwh": bill_units_kwh,
            "effective_rate_inr_per_kwh": round(rate, 2),
        },
        "summary": {
            "total_kwh_period": _r2(total_kwh),
            "estimated_cost_period_inr": _inr(cost_rules.cost_inr(total_kwh, rate)),
            "monitored_count": len(result.appliances),
            "largest_monitored_appliance_id": largest,
            "issues_count": len(issues),
        },
        "appliances": rows,
        "issues": issues,
        "signals": result.signals,
        "emissions": emissions,
        "warnings": warnings,
        "alert": {"status": alert_status},
    }
    return AnalysisResponse.model_validate(response)
