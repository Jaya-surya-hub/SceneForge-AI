"""Application exceptions and error formatting for IncuBrix Signal Room."""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse


class SignalRoomException(Exception):
    """Base exception for all Signal Room business and runtime errors."""

    def __init__(
        self,
        message: str,
        code: str = "SIGNALROOM_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class NotFoundException(SignalRoomException):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} '{identifier}' was not found.",
            code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"resource": resource, "identifier": identifier},
        )


class ProofIntegrityException(SignalRoomException):
    """Raised when SHA-256 hash or blockchain-style hash chain validation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="PROOF_INTEGRITY_VIOLATION",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class ProviderUnavailableException(SignalRoomException):
    """Raised when an external search or AI assistant provider is unavailable or restricted."""

    def __init__(self, provider: str, reason: str):
        super().__init__(
            message=f"Provider '{provider}' is unavailable: {reason}",
            code="PROVIDER_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"provider": provider, "reason": reason},
        )


def format_error_response(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
) -> JSONResponse:
    """Produces standardized JSON error payloads matching API guidelines."""
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }
    return JSONResponse(status_code=status_code, content=payload)


async def signalroom_exception_handler(request: Request, exc: SignalRoomException) -> JSONResponse:
    """FastAPI exception handler for custom SignalRoomException instances."""
    return format_error_response(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        status_code=exc.status_code,
    )
