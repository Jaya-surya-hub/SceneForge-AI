"""SQLAlchemy ORM models for SceneForge AI.

Tables: Job, Scene, RightsRecord, Metric, IdempotencyKey
All primary keys are UUIDs generated server-side.

JSON columns use sqlalchemy.types.JSON which is dialect-portable.
The Alembic migration uses JSONB for PostgreSQL directly.
UUID columns fall back to String(36) on SQLite for test compatibility.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ---------------------------------------------------------------------------
# Dialect-portable UUID column
# PostgreSQL uses native UUID; SQLite stores as String(36) for test compat.
# ---------------------------------------------------------------------------
try:
    from sqlalchemy.dialects.postgresql import UUID as _PG_UUID
    _UUID_COL = _PG_UUID(as_uuid=True)
except ImportError:
    _UUID_COL = String(36)


def _uuid_col(primary_key: bool = False, **kw):
    """Return a UUID column that works on both PostgreSQL and SQLite."""
    try:
        from sqlalchemy.dialects.postgresql import UUID as _PG_UUID
        return mapped_column(
            _PG_UUID(as_uuid=True), primary_key=primary_key, **kw
        )
    except Exception:
        return mapped_column(String(36), primary_key=primary_key, **kw)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Job(Base):
    """Persists every video-generation job and its lifecycle state."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True, unique=True, index=True
    )
    idempotency_payload_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )

    # --- State ---
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retryable: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- Timestamps (UTC) ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )
    queued_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Configuration ---
    script: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    voiceover_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    aspect_ratio: Mapped[str] = mapped_column(String(8), nullable=False, default="16:9")
    tts_adapter: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    stt_adapter: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    stock_provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="mock"
    )
    callback_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # --- Observability ---
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # --- Relationships ---
    scenes: Mapped[list["Scene"]] = relationship(
        "Scene", back_populates="job", cascade="all, delete-orphan"
    )
    rights_records: Mapped[list["RightsRecord"]] = relationship(
        "RightsRecord", back_populates="job", cascade="all, delete-orphan"
    )
    metric: Mapped[Optional["Metric"]] = relationship(
        "Metric", back_populates="job", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} status={self.status}>"


class Scene(Base):
    """A single planned scene within a job."""

    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id"), nullable=False, index=True
    )
    scene_index: Mapped[int] = mapped_column(Integer, nullable=False)
    narration_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    end_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    visual_concept: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intended_meaning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_visual_type: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )
    route: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    asset_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    qa_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    caption_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timeline_entry: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    plan_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # --- Relationships ---
    job: Mapped["Job"] = relationship("Job", back_populates="scenes")
    rights_records: Mapped[list["RightsRecord"]] = relationship(
        "RightsRecord", back_populates="scene"
    )

    __table_args__ = (
        UniqueConstraint("job_id", "scene_index", name="uq_scene_job_index"),
    )

    def __repr__(self) -> str:
        return f"<Scene job={self.job_id} idx={self.scene_index} status={self.status}>"


class RightsRecord(Base):
    """Rights and provenance record for every selected media asset."""

    __tablename__ = "rights_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id"), nullable=False, index=True
    )
    scene_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("scenes.id"), nullable=True
    )
    asset_id: Mapped[str] = mapped_column(String(256), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_asset_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    licence_name: Mapped[str] = mapped_column(String(256), nullable=False)
    licence_evidence_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    commercial_use_eligible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    attribution_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    attribution_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    sha256_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    asset_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="stock"
    )
    model_provenance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Relationships ---
    job: Mapped["Job"] = relationship("Job", back_populates="rights_records")
    scene: Mapped[Optional["Scene"]] = relationship(
        "Scene", back_populates="rights_records"
    )

    def __repr__(self) -> str:
        return f"<RightsRecord asset={self.asset_id} provider={self.provider_name}>"


class Metric(Base):
    """Performance and cost metrics for a completed job."""

    __tablename__ = "metrics"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("jobs.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    total_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_duration_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stage_timings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fallback_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qa_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    peak_memory_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    scene_coverage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    repeated_asset_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # --- Relationships ---
    job: Mapped["Job"] = relationship("Job", back_populates="metric")

    def __repr__(self) -> str:
        return f"<Metric job={self.job_id} duration_ms={self.total_duration_ms}>"


class IdempotencyKey(Base):
    """Persistent idempotency key store (supplements Redis TTL with DB durability)."""

    __tablename__ = "idempotency_keys"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    key: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    def __repr__(self) -> str:
        return f"<IdempotencyKey key={self.key} job={self.job_id}>"
