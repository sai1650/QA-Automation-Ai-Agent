"""Persist LangGraph QA workflow state and report.

Revision ID: 20261109_0003
Revises: 20261109_0002
Create Date: 2026-11-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261109_0003"
down_revision: Union[str, None] = "20261109_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "executions",
        sa.Column("qa_workflow_state", sa.JSON(), nullable=True),
    )
    op.add_column(
        "executions",
        sa.Column("qa_report", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("executions", "qa_report")
    op.drop_column("executions", "qa_workflow_state")
