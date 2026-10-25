"""IS-03 — Consistent error response schema.

Every 4xx and 5xx response from the API uses this shape:

    {
      "error": {
        "code": "MEDIA_PROVIDER_UNAVAILABLE",
        "message": "The selected media source is unavailable.",
        "retryable": true,
        "correlation_id": "req-abc-123",
        "details": {}
      }
    }

Machine-readable codes are SCREAMING_SNAKE_CASE strings.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable SCREAMING_SNAKE_CASE error code")
    message: str = Field(..., description="Human-readable error message (no stack traces)")
    retryable: bool = Field(..., description="Whether the client may safely retry")
    correlation_id: str = Field(default="", description="Request correlation ID")
    details: dict[str, Any] = Field(default_factory=dict, description="Optional extra context")


class ErrorResponse(BaseModel):
    error: ErrorDetail


def make_error_response(
    *,
    code: str,
    message: str,
    retryable: bool,
    correlation_id: str = "",
    details: Optional[dict[str, Any]] = None,
) -> ErrorResponse:
    return ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            retryable=retryable,
            correlation_id=correlation_id,
            details=details or {},
        )
    )
