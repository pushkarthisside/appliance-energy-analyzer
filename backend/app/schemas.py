import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class S3SyncHealth(BaseModel):
    state: Literal["ok", "failed_using_cache", "failed_no_cache"]
    at: str | None


class ApplianceHealth(BaseModel):
    id: str
    provenance: Literal["real_model", "synthetic_trace"]
    registry_status: Literal["go", "no_go", "candidate", "demo"]
    runtime_state: Literal["loaded", "load_failed", "inactive"]
    detail: str | None


class SampleHealth(BaseModel):
    id: Literal["typical_period", "simulated_scenario"]
    state: Literal["ready", "failed"]
    detail: str | None


class AlertHealth(BaseModel):
    enabled: bool
    topic_configured: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "not_ready"]
    ready: bool
    s3_sync: S3SyncHealth
    registry_version: int | None
    appliances: list[ApplianceHealth]
    samples: list[SampleHealth]
    alerts: AlertHealth
    upload_enabled: bool


class ConfigSample(BaseModel):
    id: Literal["typical_period", "simulated_scenario"]
    title: str
    description: str
    simulated: bool
    available: bool


class ConfigResponse(BaseModel):
    app_version: str
    window_days: int
    upload_enabled: bool
    alerts_enabled: bool
    max_upload_mb: int
    evidence_level: Literal["independent_test", "development_only", "none"]
    emissions_available: bool
    samples: list[ConfigSample]


class BillInput(BaseModel):
    amount_inr: float
    units_kwh: float

    @field_validator("amount_inr", "units_kwh")
    @classmethod
    def validate_bill_value(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0 or value > 10_000_000:
            raise ValueError("Bill values must be finite, greater than 0, and at most 10 000 000")
        return value


class SampleAnalysisRequest(BaseModel):
    sample_id: str = Field(min_length=1)
    bill: BillInput


class ApiError(BaseModel):
    code: str
    message: str
    details: dict | list | str | None = None


class ApiErrorResponse(BaseModel):
    error: ApiError


class AnalysisSource(BaseModel):
    kind: Literal["sample"]
    sample_id: Literal["typical_period", "simulated_scenario"]
    title: str
    description: str
    simulated: bool
    simulated_appliance_ids: list[str]
    evidence_level: Literal["independent_test", "development_only", "none"] | None
    validated_domain: bool


class WeekPeriod(BaseModel):
    start: str
    end: str
    valid: bool
    coverage_pct: float


class AnalysisPeriod(BaseModel):
    start: str
    end: str
    days: int
    coverage_pct: float
    weeks: dict[Literal["baseline_1", "baseline_2", "current"], WeekPeriod]


class AnalysisCost(BaseModel):
    bill_amount_inr: float
    bill_units_kwh: float
    effective_rate_inr_per_kwh: float


class AnalysisSummary(BaseModel):
    total_kwh_period: float | None
    estimated_cost_period_inr: float | None
    monitored_count: int
    largest_monitored_appliance_id: str | None
    issues_count: int


class DailyEnergy(BaseModel):
    date: str
    kwh: float | None


class ApplianceResult(BaseModel):
    id: str
    name: str
    provenance: Literal["real_model", "synthetic_trace", "residual"]
    kwh_period: float | None
    cost_period_inr: float | None
    share_pct: float | None
    coverage_pct: float | None
    weekly_kwh: dict[Literal["baseline_1", "baseline_2", "current"], float | None]
    status: Literal["typical", "unusual", "insufficient_data"] | None
    status_reason: Literal[
        "current_week_invalid", "baseline_week_invalid", "baseline_too_small"
    ] | None
    daily_kwh: list[DailyEnergy]


class SavingsRange(BaseModel):
    low: float
    mid: float
    high: float


class IssueSavings(BaseModel):
    label: str
    illustrative: bool
    kwh_per_month: SavingsRange
    inr_per_month: SavingsRange
    kg_co2e_per_month: SavingsRange | None


class Recommendation(BaseModel):
    action_id: str
    text: str


class AnalysisIssue(BaseModel):
    rank: int
    appliance_id: str
    appliance_name: str
    basis: Literal["real_model", "synthetic_trace", "simulated_scenario"]
    current_kwh: float
    baseline_kwh: float
    excess_kwh_week: float
    change_pct: float
    threshold_pct: float
    driver: Literal["longer_operating_time", "higher_power_when_on", "unclear"] | None
    driver_text: str | None
    caveats: list[str]
    recommendation: Recommendation
    savings: IssueSavings


class AnalysisSignals(BaseModel):
    window: Literal["current_week"]
    start: str
    step_minutes: int
    aggregate_w: list[float | None]
    by_appliance: dict[str, list[float | None]]


class AnalysisWarning(BaseModel):
    code: Literal["bill_rate_unusual", "appliance_unavailable"]
    message: str


class AnalysisAlert(BaseModel):
    status: Literal["sent", "failed", "disabled", "no_issues", "cooldown"]


class EmissionsMetadata(BaseModel):
    factor_kg_co2e_per_kwh: float
    source_name: str
    source_url: str
    edition: str
    publication_year: int
    geography: str
    retrieved_on: str
    verified_by: str


class AnalysisResponse(BaseModel):
    analysis_id: str
    generated_at: str
    source: AnalysisSource
    period: AnalysisPeriod
    cost: AnalysisCost
    summary: AnalysisSummary
    appliances: list[ApplianceResult]
    issues: list[AnalysisIssue]
    signals: AnalysisSignals
    emissions: EmissionsMetadata | None
    warnings: list[AnalysisWarning]
    alert: AnalysisAlert
