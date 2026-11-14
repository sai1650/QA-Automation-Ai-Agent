"""Add persistent browser inspection result fields.

Revision ID: 20261109_0002
Revises: 20261109_0001
Create Date: 2026-11-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261109_0002"
down_revision: Union[str, None] = "20261109_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "executions",
        sa.Column("duration_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "executions",
        sa.Column("final_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "executions",
        sa.Column("inspection_result", sa.JSON(), nullable=True),
    )
    op.add_column(
        "executions",
        sa.Column("artifact_metadata", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("executions", "artifact_metadata")
    op.drop_column("executions", "inspection_result")
    op.drop_column("executions", "final_url")
    op.drop_column("executions", "duration_ms")
