from typing import Literal

from pydantic import BaseModel


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
