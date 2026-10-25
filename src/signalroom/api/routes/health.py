"""Health check API route."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from signalroom.core.config import settings
from signalroom.db.session import get_db
from signalroom.models.evidence import EvidenceReference
from signalroom.schemas.health import (
    HealthDatabaseInfo,
    HealthLedgerInfo,
    HealthResponse,
    HealthStorageInfo,
)

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)) -> HealthResponse:
    """System health check endpoint verifying database, storage, and ledger state."""
    # 1. Database Ping
    db_connected = False
    dialect = "unknown"
    latency_ms = 0.0
    try:
        t0 = time.perf_counter()
        db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        db_connected = True
        dialect = db.bind.dialect.name if db.bind else "sqlite"
    except Exception:
        db_connected = False

    # 2. Storage Directory Check
    storage_writable = False
    storage_path = str(Path(settings.ARTIFACT_STORAGE_PATH).absolute())
    try:
        import os
        test_dir = Path(settings.ARTIFACT_STORAGE_PATH).absolute()
        os.makedirs(str(test_dir), exist_ok=True)
        probe_file = test_dir / ".health_probe"
        probe_file.write_text("probe", encoding="utf-8")
        probe_file.unlink(missing_ok=True)
        storage_writable = True
    except Exception:
        storage_writable = False

    # 3. Ledger record count
    total_ledger_records = 0
    ledger_verified = True
    try:
        total_ledger_records = db.query(EvidenceReference).count()
    except Exception:
        ledger_verified = False

    overall_status = "healthy" if (db_connected and storage_writable) else "degraded"

    return HealthResponse(
        status=overall_status,
        app=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        demo_mode=settings.DEMO_MODE,
        timestamp=datetime.now(timezone.utc).isoformat(),
        database=HealthDatabaseInfo(
            connected=db_connected,
            dialect=dialect,
            latency_ms=latency_ms,
        ),
        storage=HealthStorageInfo(
            writable=storage_writable,
            path=storage_path,
        ),
        ledger=HealthLedgerInfo(
            total_records=total_ledger_records,
            verified=ledger_verified,
        ),
    )
