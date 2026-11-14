"""Create initial project and execution tables.

Revision ID: 20261109_0001
Revises:
Create Date: 2026-11-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261109_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index("ix_projects_is_active", "projects", ["is_active"])
    op.create_index("ix_projects_name", "projects", ["name"])

    op.create_table(
        "executions",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "RUNNING",
                "WAITING_APPROVAL",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="execution_status",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("requirements", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_executions_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN "
            "('QUEUED', 'RUNNING', 'WAITING_APPROVAL', 'COMPLETED', "
            "'FAILED', 'CANCELLED')",
            name=op.f("ck_executions_execution_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_executions")),
    )
    op.create_index("ix_executions_created_at", "executions", ["created_at"])
    op.create_index("ix_executions_project_id", "executions", ["project_id"])
    op.create_index("ix_executions_status", "executions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_executions_status", table_name="executions")
    op.drop_index("ix_executions_project_id", table_name="executions")
    op.drop_index("ix_executions_created_at", table_name="executions")
    op.drop_table("executions")
    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_index("ix_projects_is_active", table_name="projects")
    op.drop_table("projects")
