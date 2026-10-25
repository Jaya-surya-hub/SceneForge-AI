"""SQLAlchemy model for research execution runs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from signalroom.db.base import Base

if TYPE_CHECKING:
    from signalroom.models.project import Project
    from signalroom.models.evidence import EvidenceReference


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)

    # run_type: full_discovery | replay | single_question | technical_audit
    run_type: Mapped[str] = mapped_column(String(32), default="full_discovery", index=True)

    # status: pending | running | completed | failed | partially_failed
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)

    markets: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["US", "UK", "IN"])
    assistants: Mapped[List[str]] = mapped_column(
        JSON,
        default=lambda: ["google_search", "chatgpt", "claude", "gemini", "perplexity"],
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    project: Mapped[Optional[Project]] = relationship("Project", back_populates="runs")
    evidence_records: Mapped[List[EvidenceReference]] = relationship(
        "EvidenceReference",
        back_populates="run",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Run id={self.id} type={self.run_type} status={self.status}>"
