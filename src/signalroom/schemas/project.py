"""Project Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    name: str = Field(..., max_length=255)
    slug: str = Field(..., max_length=255)
    description: Optional[str] = None
    target_domains: List[str] = Field(default_factory=lambda: ["incubrix.com"])
    default_markets: List[str] = Field(default_factory=lambda: ["US", "UK", "IN"])


class ProjectCreate(ProjectBase):
    id: Optional[str] = Field(default=None, max_length=64)


class ProjectRead(ProjectBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
