from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.errors import error_response
from app.schemas import AnalysisResponse, ApiErrorResponse, SampleAnalysisRequest

router = APIRouter(prefix="/api")


@router.post(
    "/analyze/sample",
    response_model=AnalysisResponse,
    responses={
        404: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        503: {"model": ApiErrorResponse},
    },
)
async def analyze_sample(request: SampleAnalysisRequest) -> JSONResponse:
    """Validate the frozen request contract and report unavailable analysis honestly."""
    if request.sample_id not in {"typical_period", "simulated_scenario"}:
        return error_response("unknown_sample", "Unknown sample_id", 404)

    # The analysis engine and sample artifacts are not present in this checkout.
    # Architecture defines run_pipeline(bundle) -> bill-independent PipelineResult;
    # bundle/result types and the import path need agreement with the engine owner.
    return error_response(
        "not_ready", "Sample analysis is unavailable until the pipeline is integrated", 503
    )
