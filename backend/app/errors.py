import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger("aea.errors")


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": None}},
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    if request.url.path == "/api/analyze/sample":
        sample_error = any("sample_id" in error.get("loc", ()) for error in errors)
        if sample_error:
            return error_response("unknown_sample", "sample_id is required", 404)
        return error_response(
            "invalid_bill",
            "Bill values must be finite, greater than 0, and at most 10 000 000",
            422,
        )
    return error_response("internal", "Request validation failed", 422)


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Unexpected errors: log the details, return no internals (ARCHITECTURE.md §15.4)."""
    log.exception("unhandled error on %s", request.url.path)
    return error_response("internal", "An unexpected error occurred", 500)
