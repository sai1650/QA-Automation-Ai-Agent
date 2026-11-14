"""Add persistent AI evaluation experiment reports.

Revision ID: 20261109_0004
Revises: 20261109_0003
Create Date: 2026-11-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261109_0004"
down_revision: Union[str, None] = "20261109_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_experiments",
        sa.Column("experiment_name", sa.String(length=160), nullable=False),
        sa.Column("dataset_id", sa.String(length=64), nullable=False),
        sa.Column("dataset_version", sa.String(length=32), nullable=False),
        sa.Column("agent_name", sa.String(length=40), nullable=False),
        sa.Column("provider_mode", sa.String(length=20), nullable=False),
        sa.Column("provider_name", sa.String(length=40), nullable=False),
        sa.Column("model_identifier", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("rag_enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("sample_results", sa.JSON(), nullable=False),
        sa.Column("total_samples", sa.Integer(), nullable=False),
        sa.Column("completed_samples", sa.Integer(), nullable=False),
        sa.Column("failed_samples", sa.Integer(), nullable=False),
        sa.Column("skipped_samples", sa.Integer(), nullable=False),
        sa.Column("run_count", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation_experiments")),
    )
    op.create_index(
        "ix_evaluation_experiments_created_at",
        "evaluation_experiments",
        ["created_at"],
    )
    op.create_index(
        "ix_evaluation_experiments_dataset_created",
        "evaluation_experiments",
        ["dataset_id", "created_at"],
    )
    op.create_index(
        "ix_evaluation_experiments_agent_created",
        "evaluation_experiments",
        ["agent_name", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_evaluation_experiments_agent_created",
        table_name="evaluation_experiments",
    )
    op.drop_index(
        "ix_evaluation_experiments_dataset_created",
        table_name="evaluation_experiments",
    )
    op.drop_index(
        "ix_evaluation_experiments_created_at",
        table_name="evaluation_experiments",
    )
    op.drop_table("evaluation_experiments")
