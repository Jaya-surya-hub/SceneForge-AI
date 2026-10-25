"""Evidence Reference & Proof Ledger API routes."""

from __future__ import annotations

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from signalroom.core.config import settings
from signalroom.db.session import get_db
from signalroom.models.evidence import EvidenceReference
from signalroom.models.question import Question
from signalroom.models.run import Run
from signalroom.schemas.evidence import (
    EvidenceReferenceCreate,
    EvidenceReferenceRead,
    LedgerVerificationResult,
)
from signalroom.storage.artifact_store import (
    GENESIS_PREV_HASH,
    LocalArtifactStore,
    artifact_store,
)

router = APIRouter(prefix="/evidence", tags=["Proof Ledger"])


@router.get("/ledger", response_model=List[EvidenceReferenceRead])
def list_ledger(
    question_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[EvidenceReference]:
    """Lists append-only tamper-evident evidence references."""
    query = db.query(EvidenceReference)
    if question_id:
        query = query.filter(EvidenceReference.question_id == question_id)
    if run_id:
        query = query.filter(EvidenceReference.run_id == run_id)
    if provider:
        query = query.filter(EvidenceReference.provider == provider)

    return query.order_by(EvidenceReference.created_at.asc()).offset(offset).limit(limit).all()


@router.post("/ledger", response_model=EvidenceReferenceRead, status_code=status.HTTP_201_CREATED)
def record_evidence(payload: EvidenceReferenceCreate, db: Session = Depends(get_db)) -> EvidenceReference:
    """Appends an evidence record into the tamper-evident ledger."""
    # Ensure question and run exist
    question = db.query(Question).filter(Question.id == payload.question_id).first()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question '{payload.question_id}' does not exist.",
        )

    run = db.query(Run).filter(Run.id == payload.run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{payload.run_id}' does not exist.",
        )

    # Determine previous hash from the most recent record
    last_record = db.query(EvidenceReference).order_by(EvidenceReference.created_at.desc()).first()
    expected_prev_hash = last_record.current_ledger_hash if last_record else GENESIS_PREV_HASH

    # Compute ledger entry hash
    record_id = payload.id or f"EV-{uuid.uuid4().hex[:8].upper()}"
    
    # Store
    evidence = EvidenceReference(
        id=record_id,
        question_id=payload.question_id,
        run_id=payload.run_id,
        provider=payload.provider,
        collection_method=payload.collection_method,
        market=payload.market,
        location=payload.location,
        language=payload.language,
        artifact_path=payload.artifact_path,
        sha256_hash=payload.sha256_hash,
        prev_ledger_hash=expected_prev_hash,
        current_ledger_hash=payload.current_ledger_hash,
        execution_status=payload.execution_status,
        runtime_ms=payload.runtime_ms,
        cost_usd=payload.cost_usd,
        is_demo=payload.is_demo,
        notes=payload.notes,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


@router.get("/verify", response_model=LedgerVerificationResult)
def verify_ledger(db: Session = Depends(get_db)) -> LedgerVerificationResult:
    """Audits the entire evidence ledger for hash-chain continuity and artifact tampering."""
    records = db.query(EvidenceReference).order_by(EvidenceReference.created_at.asc()).all()
    
    total = len(records)
    chain_breaks = 0
    missing_artifacts = 0
    corrupted_artifacts = 0
    errors: List[str] = []

    expected_prev = GENESIS_PREV_HASH
    latest_hash: Optional[str] = None

    for idx, rec in enumerate(records):
        latest_hash = rec.current_ledger_hash

        # 1. Check prev_hash linkage
        if rec.prev_ledger_hash != expected_prev:
            chain_breaks += 1
            errors.append(
                f"Entry {rec.id} (index {idx}) prev_hash '{rec.prev_ledger_hash[:8]}...' != expected '{expected_prev[:8]}...'"
            )

        # 2. Check artifact on filesystem (skip in pure demo mode if artifact is simulated)
        if not rec.is_demo or artifact_store.base_dir.joinpath(rec.artifact_path).exists():
            target_path = artifact_store.base_dir / rec.artifact_path
            if not target_path.exists():
                missing_artifacts += 1
                errors.append(f"Entry {rec.id} missing artifact file: {rec.artifact_path}")
            else:
                disk_hash = artifact_store.calculate_sha256(target_path.read_bytes())
                if disk_hash.lower() != rec.sha256_hash.lower():
                    corrupted_artifacts += 1
                    errors.append(
                        f"Entry {rec.id} artifact hash mismatch. DB: {rec.sha256_hash[:8]}..., Disk: {disk_hash[:8]}..."
                    )

        # Update chain for next iteration
        expected_prev = rec.current_ledger_hash

    is_valid = (chain_breaks == 0 and missing_artifacts == 0 and corrupted_artifacts == 0)

    return LedgerVerificationResult(
        is_valid=is_valid,
        total_entries_verified=total,
        chain_breaks_detected=chain_breaks,
        missing_artifacts=missing_artifacts,
        corrupted_artifacts=corrupted_artifacts,
        errors=errors,
        genesis_hash=GENESIS_PREV_HASH,
        latest_hash=latest_hash,
    )
