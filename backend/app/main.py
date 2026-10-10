import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from app.alerts import AlertService
from app.api.routes import router as api_router
from app.config import Settings
from app.errors import internal_error_handler, validation_error_handler
from app.runtime import build_runtime

APP_VERSION = "0.1.0"


def create_app(settings: Settings | None = None, s3_client=None, sns_client_factory=None) -> FastAPI:
    """Build the application. Startup (artifact sync, model loading, sample precompute)
    runs once in the lifespan; requests only read the cached results."""
    settings = settings or Settings.from_env()
    logging.basicConfig(level=settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = build_runtime(settings, s3_client)
        app.state.alerts = AlertService(settings, sns_client_factory)
        yield

    app = FastAPI(title="Appliance Energy Analyzer", version=APP_VERSION, lifespan=lifespan)
    app.state.settings = settings
    app.state.runtime = None  # until startup completes: not_ready
    app.state.alerts = AlertService(settings, sns_client_factory)
    app.include_router(api_router)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, internal_error_handler)

    frontend_dir = settings.frontend_dir.resolve()
    if frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    return app


app = create_app()
