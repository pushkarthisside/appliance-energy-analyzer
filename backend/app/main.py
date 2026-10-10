import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import HealthResponse

app = FastAPI(title="Appliance Energy Analyzer", version="0.1.0")


@app.get("/api/health", response_model=HealthResponse, responses={503: {"model": HealthResponse}})
async def health() -> JSONResponse:
    """Report not-ready until artifact loading and sample precomputation exist."""
    health = HealthResponse(
        status="not_ready",
        ready=False,
        s3_sync={"state": "failed_no_cache", "at": None},
        registry_version=None,
        appliances=[],
        samples=[
            {
                "id": "typical_period",
                "state": "failed",
                "detail": "Artifact and sample startup is not implemented yet.",
            },
            {
                "id": "simulated_scenario",
                "state": "failed",
                "detail": "Artifact and sample startup is not implemented yet.",
            },
        ],
        alerts={"enabled": False, "topic_configured": False},
        upload_enabled=False,
    )
    return JSONResponse(status_code=503, content=health.model_dump(mode="json"))


frontend_dir = Path(
    os.environ.get(
        "AEA_FRONTEND_DIR",
        str(Path(__file__).resolve().parents[2] / "frontend" / "dist"),
    )
).resolve()
if frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
