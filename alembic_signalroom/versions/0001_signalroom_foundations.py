"""Signal Room foundations migration

Revision ID: 0001_signalroom_foundations
Revises: 
Create Date: 2026-10-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_signalroom_foundations"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Projects Table
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_domains", sa.JSON(), nullable=False),
        sa.Column("default_markets", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_id", "projects", ["id"], unique=False)
    op.create_index("ix_projects_slug", "projects", ["slug"], unique=True)

    # 2. Questions Table
    op.create_table(
        "questions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("journey_stage", sa.String(length=32), nullable=False),
        sa.Column("search_intent", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("target_market", sa.String(length=8), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_questions_id", "questions", ["id"], unique=False)
    op.create_index("ix_questions_journey_stage", "questions", ["journey_stage"], unique=False)
    op.create_index("ix_questions_search_intent", "questions", ["search_intent"], unique=False)
    op.create_index("ix_questions_target_market", "questions", ["target_market"], unique=False)

    # 3. Runs Table
    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("run_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("markets", sa.JSON(), nullable=False),
        sa.Column("assistants", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_cost_usd", sa.Float(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_runs_id", "runs", ["id"], unique=False)
    op.create_index("ix_runs_run_type", "runs", ["run_type"], unique=False)
    op.create_index("ix_runs_status", "runs", ["status"], unique=False)

    # 4. Evidence References Table
    op.create_table(
        "evidence_references",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("question_id", sa.String(length=64), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("collection_method", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("market", sa.String(length=8), nullable=False),
        sa.Column("location", sa.String(length=128), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("artifact_path", sa.String(length=512), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("prev_ledger_hash", sa.String(length=64), nullable=False),
        sa.Column("current_ledger_hash", sa.String(length=64), nullable=False),
        sa.Column("execution_status", sa.String(length=32), nullable=False),
        sa.Column("runtime_ms", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evidence_references_id", "evidence_references", ["id"], unique=False)
    op.create_index("ix_evidence_references_question_id", "evidence_references", ["question_id"], unique=False)
    op.create_index("ix_evidence_references_run_id", "evidence_references", ["run_id"], unique=False)
    op.create_index("ix_evidence_references_provider", "evidence_references", ["provider"], unique=False)
    op.create_index("ix_evidence_references_current_ledger_hash", "evidence_references", ["current_ledger_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("evidence_references")
    op.drop_table("runs")
    op.drop_table("questions")
    op.drop_table("projects")
