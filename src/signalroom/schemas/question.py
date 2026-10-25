"""Question Pydantic schemas for Question Atlas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class QuestionBase(BaseModel):
    text: str = Field(..., min_length=5, description="Full creator question text")
    journey_stage: str = Field(..., description="Make | Repurpose | Edit | Caption | Publish | Grow")
    search_intent: str = Field(..., description="informational | comparison | commercial")
    source_type: str = Field(..., description="google_autocomplete | paa | forum_reddit | keyword_planner")
    source_url: str = Field(..., description="Verifiable URL of origin")
    target_market: str = Field(default="US", max_length=8)
    language: str = Field(default="en", max_length=8)
    notes: Optional[str] = None
    is_demo: bool = Field(default=False, description="True if this is an illustrative/sample question")


class QuestionCreate(QuestionBase):
    id: Optional[str] = Field(default=None, max_length=64)
    project_id: Optional[str] = None


class QuestionRead(QuestionBase):
    id: str
    project_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
