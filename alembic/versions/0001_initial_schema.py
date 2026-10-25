"""Initial schema: jobs, scenes, rights_records, metrics, idempotency_keys.

Revision ID: 0001
Revises:
Create Date: 2026-10-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- jobs ---
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(256), nullable=True),
        sa.Column("idempotency_payload_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retryable", sa.Boolean, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("script", sa.Text, nullable=True),
        sa.Column("voiceover_path", sa.String(512), nullable=True),
        sa.Column("aspect_ratio", sa.String(8), nullable=False, server_default="16:9"),
        sa.Column("tts_adapter", sa.String(32), nullable=False, server_default="mock"),
        sa.Column("stt_adapter", sa.String(32), nullable=False, server_default="mock"),
        sa.Column(
            "stock_provider", sa.String(32), nullable=False, server_default="mock"
        ),
        sa.Column("callback_url", sa.String(512), nullable=True),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_jobs_idempotency_key", "jobs", ["idempotency_key"])
    op.create_index("ix_jobs_status", "jobs", ["status"])

    # --- scenes ---
    op.create_table(
        "scenes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scene_index", sa.Integer, nullable=False),
        sa.Column("narration_text", sa.Text, nullable=True),
        sa.Column("start_time", sa.Float, nullable=True),
        sa.Column("end_time", sa.Float, nullable=True),
        sa.Column("visual_concept", sa.Text, nullable=True),
        sa.Column("intended_meaning", sa.Text, nullable=True),
        sa.Column("suggested_visual_type", sa.String(32), nullable=True),
        sa.Column("route", sa.String(32), nullable=True),
        sa.Column("asset_id", sa.String(256), nullable=True),
        sa.Column("relevance_score", sa.Float, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("qa_status", sa.String(16), nullable=True),
        sa.Column("caption_text", sa.Text, nullable=True),
        sa.Column("timeline_entry", postgresql.JSONB, nullable=True),
        sa.Column("plan_data", postgresql.JSONB, nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "scene_index", name="uq_scene_job_index"),
    )
    op.create_index("ix_scenes_job_id", "scenes", ["job_id"])

    # --- rights_records ---
    op.create_table(
        "rights_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scene_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("asset_id", sa.String(256), nullable=False),
        sa.Column("provider_name", sa.String(128), nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("provider_asset_url", sa.Text, nullable=True),
        sa.Column("licence_name", sa.String(256), nullable=False),
        sa.Column("licence_evidence_url", sa.Text, nullable=True),
        sa.Column(
            "commercial_use_eligible", sa.Boolean, nullable=False, server_default="false"
        ),
        sa.Column(
            "attribution_required", sa.Boolean, nullable=False, server_default="false"
        ),
        sa.Column("attribution_text", sa.Text, nullable=True),
        sa.Column(
            "retrieved_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("sha256_hash", sa.String(64), nullable=True),
        sa.Column(
            "asset_type", sa.String(32), nullable=False, server_default="stock"
        ),
        sa.Column("model_provenance", sa.Text, nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["scene_id"], ["scenes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rights_records_job_id", "rights_records", ["job_id"])

    # --- metrics ---
    op.create_table(
        "metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("total_duration_ms", sa.Integer, nullable=True),
        sa.Column("output_duration_s", sa.Float, nullable=True),
        sa.Column("stage_timings", postgresql.JSONB, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fallback_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("qa_passed", sa.Boolean, nullable=True),
        sa.Column("cost_usd", sa.Float, nullable=True),
        sa.Column("peak_memory_mb", sa.Float, nullable=True),
        sa.Column("scene_coverage", sa.Float, nullable=True),
        sa.Column("repeated_asset_rate", sa.Float, nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("raw_data", postgresql.JSONB, nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )

    # --- idempotency_keys ---
    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(256), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_idempotency_keys_key", "idempotency_keys", ["key"])


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_table("metrics")
    op.drop_table("rights_records")
    op.drop_table("scenes")
    op.drop_table("jobs")
