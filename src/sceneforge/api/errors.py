"""Global exception handlers — maps domain errors to IS-03 error response schema.

No stack traces are returned to callers. All exceptions produce:
  {"error": {"code": "...", "message": "...", "retryable": bool,
             "correlation_id": "...", "details": {}}}
"""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from sceneforge.observability.logging import get_correlation_id, get_logger
from sceneforge.schemas.errors import make_error_response
from sceneforge.schemas.exceptions import SceneForgeError

log = get_logger(__name__)


async def sceneforge_exception_handler(
    request: Request, exc: SceneForgeError
) -> JSONResponse:
    cid = get_correlation_id()
    log.warning(
        "domain_error",
        code=exc.code,
        message=exc.message,
        http_status=exc.http_status,
        path=str(request.url),
    )
    return JSONResponse(
        status_code=exc.http_status,
        content=make_error_response(
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
            correlation_id=cid,
            details=exc.details,
        ).model_dump(),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    cid = get_correlation_id()
    # Flatten pydantic errors into a safe string — no internal paths exposed
    errors = [
        {"loc": e["loc"], "msg": e["msg"]}
        for e in exc.errors()
    ]
    log.info("request_validation_error", path=str(request.url), errors=errors)
    return JSONResponse(
        status_code=422,
        content=make_error_response(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            retryable=False,
            correlation_id=cid,
            details={"errors": errors},
        ).model_dump(),
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    cid = get_correlation_id()
    # Log full traceback internally, return safe message externally
    log.exception(
        "unhandled_exception",
        path=str(request.url),
        exc_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content=make_error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred. Please try again later.",
            retryable=True,
            correlation_id=cid,
        ).model_dump(),
    )
