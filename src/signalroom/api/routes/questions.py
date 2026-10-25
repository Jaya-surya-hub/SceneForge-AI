"""Questions API routes for Question Atlas."""

from __future__ import annotations

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from signalroom.db.session import get_db
from signalroom.models.question import Question
from signalroom.schemas.question import QuestionCreate, QuestionRead

router = APIRouter(prefix="/questions", tags=["Question Atlas"])


@router.get("", response_model=List[QuestionRead])
def list_questions(
    journey_stage: Optional[str] = Query(None, description="Make | Repurpose | Edit | Caption | Publish | Grow"),
    search_intent: Optional[str] = Query(None, description="informational | comparison | commercial"),
    market: Optional[str] = Query(None, description="US | UK | IN"),
    is_demo: Optional[bool] = Query(None, description="Filter demo questions"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[Question]:
    """Lists questions in the Question Atlas with optional filtering."""
    query = db.query(Question)
    if journey_stage:
        query = query.filter(Question.journey_stage == journey_stage)
    if search_intent:
        query = query.filter(Question.search_intent == search_intent)
    if market:
        query = query.filter(Question.target_market == market)
    if is_demo is not None:
        query = query.filter(Question.is_demo == is_demo)

    return query.order_by(Question.created_at.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=QuestionRead, status_code=status.HTTP_201_CREATED)
def create_question(payload: QuestionCreate, db: Session = Depends(get_db)) -> Question:
    """Creates a new question with verifiable source attribution."""
    question_id = payload.id or f"Q-{uuid.uuid4().hex[:6].upper()}"
    existing = db.query(Question).filter(Question.id == question_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Question with ID '{question_id}' already exists.",
        )

    question = Question(
        id=question_id,
        project_id=payload.project_id,
        text=payload.text,
        journey_stage=payload.journey_stage,
        search_intent=payload.search_intent,
        source_type=payload.source_type,
        source_url=payload.source_url,
        target_market=payload.target_market,
        language=payload.language,
        notes=payload.notes,
        is_demo=payload.is_demo,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.get("/{question_id}", response_model=QuestionRead)
def get_question(question_id: str, db: Session = Depends(get_db)) -> Question:
    """Retrieves a single question by ID."""
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Question '{question_id}' not found.")
    return question
