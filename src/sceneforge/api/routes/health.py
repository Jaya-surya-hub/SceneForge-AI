"""Health and readiness endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from sceneforge.api.dependencies import get_db, get_redis
from sceneforge.jobs.schemas import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
async def health() -> HealthResponse:
    """Returns 200 if the API process is alive."""
    return HealthResponse(
        status="ok",
        version=os.getenv("API_VERSION", "0.1.0"),
        environment=os.getenv("ENVIRONMENT", "development"),
    )


@router.get("/ready", response_model=ReadyResponse, summary="Readiness check")
async def ready(db: Session = Depends(get_db)) -> ReadyResponse:
    """Returns 200 if all dependencies are reachable."""
    checks: dict[str, str] = {}

    # Database
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"

    # Redis — skip in test mode to avoid hanging
    import os
    if os.getenv("SKIP_STARTUP_CHECKS", "false").lower() != "true":
        try:
            r = get_redis()
            r.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {type(exc).__name__}"
    else:
        checks["redis"] = "skipped (test mode)"

    overall = "ok" if all(v in ("ok", "skipped (test mode)") for v in checks.values()) else "degraded"
    return ReadyResponse(status=overall, checks=checks)
