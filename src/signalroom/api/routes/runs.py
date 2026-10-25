"""Runs API routes for measurement orchestration."""

from __future__ import annotations

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from signalroom.db.session import get_db
from signalroom.models.run import Run
from signalroom.schemas.run import RunCreate, RunRead

router = APIRouter(prefix="/runs", tags=["Runs"])


@router.get("", response_model=List[RunRead])
def list_runs(
    status: Optional[str] = Query(None, description="pending | running | completed | failed"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> List[Run]:
    """Lists measurement runs."""
    query = db.query(Run)
    if status:
        query = query.filter(Run.status == status)
    return query.order_by(Run.started_at.desc()).limit(limit).all()


@router.post("", response_model=RunRead, status_code=status.HTTP_201_CREATED)
def create_run(payload: RunCreate, db: Session = Depends(get_db)) -> Run:
    """Registers a new measurement run."""
    run_id = payload.id or f"RUN-{uuid.uuid4().hex[:8].upper()}"
    existing = db.query(Run).filter(Run.id == run_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run with ID '{run_id}' already exists.",
        )

    run = Run(
        id=run_id,
        project_id=payload.project_id,
        run_type=payload.run_type,
        status=payload.status,
        markets=payload.markets,
        assistants=payload.assistants,
        total_cost_usd=payload.total_cost_usd,
        error_summary=payload.error_summary,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/{run_id}", response_model=RunRead)
def get_run(run_id: str, db: Session = Depends(get_db)) -> Run:
    """Retrieves a single run by ID."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' not found.")
    return run
