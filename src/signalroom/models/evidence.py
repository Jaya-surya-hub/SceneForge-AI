"""SQLAlchemy model for Proof Ledger evidence references."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from signalroom.db.base import Base

if TYPE_CHECKING:
    from signalroom.models.question import Question
    from signalroom.models.run import Run


class EvidenceReference(Base):
    """Tamper-evident append-only Proof Ledger entry.
    
    Each record links an artifact to a question and run, with SHA-256 hashing
    and cryptographic chaining to verify that historical observations have not been altered.
    """
    __tablename__ = "evidence_references"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    question_id: Mapped[str] = mapped_column(String(64), ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id", ondelete="CASCADE"), index=True)

    # Provider and collection method
    provider: Mapped[str] = mapped_column(String(64), index=True)  # e.g., google_search, chatgpt, claude, gemini, perplexity
    collection_method: Mapped[str] = mapped_column(String(64))      # e.g., official_api, manual_capture, browser_fixture

    # Temporal and geographical metadata
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    market: Mapped[str] = mapped_column(String(8), default="US", index=True)
    location: Mapped[str] = mapped_column(String(128), default="United States")
    language: Mapped[str] = mapped_column(String(8), default="en")

    # Cryptographic proof & artifact metadata
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prev_ledger_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    current_ledger_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # Execution telemetry
    execution_status: Mapped[str] = mapped_column(String(32), default="success", index=True)  # success | failed | restricted
    runtime_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Demarcation of demo/sample records vs live records
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    question: Mapped[Question] = relationship("Question", back_populates="evidence_records")
    run: Mapped[Run] = relationship("Run", back_populates="evidence_records")

    def __repr__(self) -> str:
        return f"<EvidenceReference id={self.id} q={self.question_id} provider={self.provider} hash={self.current_ledger_hash[:8]}>"
