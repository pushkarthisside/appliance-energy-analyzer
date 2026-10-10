from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.errors import error_response
from app.ingest.bundle import SAMPLE_IDS
from app.pipeline import apply_bill, complete_emissions
from app.schemas import (
    AnalysisAlert,
    AnalysisResponse,
    ApiErrorResponse,
    ConfigResponse,
    HealthResponse,
    SampleAnalysisRequest,
)

router = APIRouter(prefix="/api")

APP_VERSION = "0.1.0"
TYPICAL_PERIOD_PLACEHOLDER = {
    "title": "Typical period",
    "description": "Real-data demonstration, available only when a real appliance model passes the frozen evaluation criteria.",
    "simulated": False,
}


def _runtime(request: Request):
    return getattr(request.app.state, "runtime", None)


@router.get("/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
def health(request: Request) -> JSONResponse:
    runtime = _runtime(request)
    settings = request.app.state.settings
    alerts = {"enabled": settings.alerts_active, "topic_configured": bool(settings.sns_topic_arn)}
    if runtime is None:
        body = HealthResponse(
            status="not_ready", ready=False, s3_sync={"state": "failed_no_cache", "at": None},
            registry_version=None, appliances=[], samples=[], alerts=alerts,
            upload_enabled=settings.enable_upload,
        )
        return JSONResponse(status_code=503, content=body.model_dump(mode="json"))

    appliances = []
    if runtime.registry is not None:
        for entry in runtime.registry.entries.values():
            if entry.status in ("candidate", "no_go"):
                state, detail = "inactive", None
            elif entry.id in runtime.adapter_failures:
                state, detail = "load_failed", runtime.adapter_failures[entry.id]
            else:
                state, detail = "loaded", None
            appliances.append(
                {"id": entry.id, "provenance": entry.provenance, "registry_status": entry.status,
                 "runtime_state": state, "detail": detail}
            )
    body = HealthResponse(
        status=runtime.status,
        ready=runtime.ready,
        s3_sync={"state": runtime.sync.state, "at": runtime.sync.at},
        registry_version=runtime.registry.registry_version if runtime.registry else None,
        appliances=appliances,
        samples=[{"id": s.id, "state": s.state, "detail": s.detail} for s in runtime.samples.values()],
        alerts=alerts,
        upload_enabled=settings.enable_upload,
    )
    return JSONResponse(status_code=200 if runtime.ready else 503, content=body.model_dump(mode="json"))


@router.get("/config", response_model=ConfigResponse, responses={503: {"model": ApiErrorResponse}})
def config(request: Request):
    runtime = _runtime(request)
    if runtime is None or not runtime.ready:
        return error_response("not_ready", "The analysis service is still starting", 503)
    settings = request.app.state.settings
    samples = []
    for sample_id in SAMPLE_IDS:
        state = runtime.samples.get(sample_id)
        if state is not None and state.result is not None:
            r = state.result
            samples.append({"id": sample_id, "title": r.title, "description": r.description,
                            "simulated": r.simulated, "available": state.state == "ready"})
        elif sample_id == "typical_period":
            samples.append({"id": sample_id, **TYPICAL_PERIOD_PLACEHOLDER, "available": False})
        else:
            samples.append({"id": sample_id, "title": "Simulated scenario",
                            "description": state.detail if state else "Not built.",
                            "simulated": True, "available": False})
    return ConfigResponse(
        app_version=APP_VERSION, window_days=21, upload_enabled=settings.enable_upload,
        alerts_enabled=settings.alerts_active, max_upload_mb=settings.max_upload_mb,
        evidence_level=runtime.evidence_level,
        emissions_available=complete_emissions(runtime.emissions) is not None,
        samples=samples,
    )


@router.post(
    "/analyze/sample",
    response_model=AnalysisResponse,
    responses={404: {"model": ApiErrorResponse}, 422: {"model": ApiErrorResponse}, 503: {"model": ApiErrorResponse}},
)
def analyze_sample(payload: SampleAnalysisRequest, request: Request):
    """Apply the bill to the cached, bill-independent pipeline result (§15.2)."""
    if payload.sample_id not in SAMPLE_IDS:
        return error_response("unknown_sample", "Unknown sample_id", 404)
    runtime = _runtime(request)
    if runtime is None or not runtime.ready:
        return error_response("not_ready", "The analysis service is still starting", 503)
    state = runtime.samples.get(payload.sample_id)
    if state is None or state.state != "ready" or state.result is None:
        return error_response("sample_unavailable", "This sample is not available", 503)
    try:
        response = apply_bill(
            state.result, payload.bill.amount_inr, payload.bill.units_kwh,
            runtime.actions, runtime.emissions,
        )
    except ValueError as exc:
        if str(exc) == "invalid_bill":
            return error_response("invalid_bill", "Bill values must be finite, greater than 0, and at most 10 000 000", 422)
        raise
    response.alert = AnalysisAlert(status=request.app.state.alerts.publish(response))
    return response


@router.get("/evaluation", responses={404: {"model": ApiErrorResponse}})
def evaluation(request: Request):
    """Serve evaluation.json unchanged (§6.6)."""
    runtime = _runtime(request)
    if runtime is None or runtime.evaluation is None:
        return error_response("evaluation_unavailable", "Evaluation results are not available", 404)
    return JSONResponse(content=runtime.evaluation)


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
def unknown_api_route(path: str):
    """Unmatched /api/* paths return JSON 404, never the frontend (API-04)."""
    return error_response("not_found", f"No API route /api/{path}", 404)
