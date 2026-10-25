"""Run Pydantic schemas for measurement orchestration."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class RunBase(BaseModel):
    run_type: str = Field(default="full_discovery", description="full_discovery | replay | single_question | audit")
    status: str = Field(default="pending", description="pending | running | completed | failed | partially_failed")
    markets: List[str] = Field(default_factory=lambda: ["US", "UK", "IN"])
    assistants: List[str] = Field(
        default_factory=lambda: ["google_search", "chatgpt", "claude", "gemini", "perplexity"]
    )
    total_cost_usd: float = Field(default=0.0)
    error_summary: Optional[str] = None


class RunCreate(RunBase):
    id: Optional[str] = Field(default=None, max_length=64)
    project_id: Optional[str] = None


class RunRead(RunBase):
    id: str
    project_id: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
