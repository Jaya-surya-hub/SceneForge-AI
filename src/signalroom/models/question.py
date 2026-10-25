"""SQLAlchemy model for genuine creator questions in Question Atlas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from signalroom.db.base import Base

if TYPE_CHECKING:
    from signalroom.models.project import Project
    from signalroom.models.evidence import EvidenceReference


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    
    text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Journey stage: Make | Repurpose | Edit | Caption | Publish | Grow
    journey_stage: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    
    # Search intent: informational | comparison | commercial
    search_intent: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    
    # Genuine source provenance
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    
    target_market: Mapped[str] = mapped_column(String(8), default="US", index=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    project: Mapped[Optional[Project]] = relationship("Project", back_populates="questions")
    evidence_records: Mapped[List[EvidenceReference]] = relationship(
        "EvidenceReference",
        back_populates="question",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Question id={self.id} stage={self.journey_stage} text='{self.text[:30]}...'>"
