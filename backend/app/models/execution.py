from datetime import datetime
from enum import Enum
from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class ExecutionStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


_STATUS_VALUES_SQL = ", ".join(
    f"'{status.value}'" for status in ExecutionStatus
)


class Execution(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "executions"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_STATUS_VALUES_SQL})",
            name="execution_status",
        ),
        Index("ix_executions_project_id", "project_id"),
        Index("ix_executions_status", "status"),
        Index("ix_executions_created_at", "created_at"),
    )

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        SQLAlchemyEnum(
            ExecutionStatus,
            name="execution_status",
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
        ),
        default=ExecutionStatus.QUEUED,
        nullable=False,
    )
    requirements: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="CURRENT_TIMESTAMP",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    inspection_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    artifact_metadata: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    qa_workflow_state: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    qa_report: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    project: Mapped["Project"] = relationship(back_populates="executions")
