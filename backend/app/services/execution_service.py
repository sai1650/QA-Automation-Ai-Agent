from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationException
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.schemas.execution import ExecutionCreate


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


_ALLOWED_TRANSITIONS: dict[ExecutionStatus, frozenset[ExecutionStatus]] = {
    ExecutionStatus.QUEUED: frozenset({ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED}),
    ExecutionStatus.RUNNING: frozenset(
        {
            ExecutionStatus.WAITING_APPROVAL,
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
        }
    ),
    ExecutionStatus.WAITING_APPROVAL: frozenset(
        {
            ExecutionStatus.RUNNING,
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
        }
    ),
    ExecutionStatus.COMPLETED: frozenset(),
    ExecutionStatus.FAILED: frozenset(),
    ExecutionStatus.CANCELLED: frozenset(),
}


def validate_transition(
    current: ExecutionStatus,
    target: ExecutionStatus,
) -> None:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise ApplicationException(
            f"Execution cannot transition from {current.value} to {target.value}.",
            status_code=409,
            code="invalid_execution_transition",
        )


def create_execution(
    session: Session,
    project_id: UUID,
    payload: ExecutionCreate,
) -> Execution:
    if not payload.authorized_target_confirmation:
        raise ApplicationException(
            "Authorization must be confirmed.",
            status_code=422,
            code="authorization_required",
        )
    project = session.scalar(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    if project is None:
        raise ApplicationException(
            "Project not found.", status_code=404, code="project_not_found"
        )
    if not project.is_active:
        raise ApplicationException(
            "Cannot create an execution for an archived project.",
            status_code=409,
            code="project_archived",
        )

    execution = Execution(
        project_id=project_id,
        status=ExecutionStatus.QUEUED,
        requirements=payload.requirements,
        options=payload.options or {},
    )
    try:
        session.add(execution)
        session.commit()
        session.refresh(execution)
    except Exception:
        session.rollback()
        raise
    return execution


def list_executions(
    session: Session,
    *,
    project_id: UUID | None,
    status: ExecutionStatus | None,
    offset: int,
    limit: int,
    sort_order: SortOrder,
) -> tuple[list[Execution], int]:
    filters = []
    if project_id is not None:
        filters.append(Execution.project_id == project_id)
    if status is not None:
        filters.append(Execution.status == status)

    total = session.scalar(
        select(func.count()).select_from(Execution).where(*filters)
    )
    ordering = (
        (Execution.created_at.asc(), Execution.id.asc())
        if sort_order is SortOrder.ASC
        else (Execution.created_at.desc(), Execution.id.desc())
    )
    executions = list(
        session.scalars(
            select(Execution)
            .where(*filters)
            .order_by(*ordering)
            .offset(offset)
            .limit(limit)
        )
    )
    return executions, total or 0


def list_project_executions(
    session: Session,
    project_id: UUID,
    *,
    status: ExecutionStatus | None,
    offset: int,
    limit: int,
    sort_order: SortOrder,
) -> tuple[list[Execution], int]:
    if session.get(Project, project_id) is None:
        raise ApplicationException(
            "Project not found.", status_code=404, code="project_not_found"
        )
    return list_executions(
        session,
        project_id=project_id,
        status=status,
        offset=offset,
        limit=limit,
        sort_order=sort_order,
    )


def get_execution(session: Session, execution_id: UUID) -> Execution:
    execution = session.get(Execution, execution_id)
    if execution is None:
        raise ApplicationException(
            "Execution not found.",
            status_code=404,
            code="execution_not_found",
        )
    return execution


def cancel_execution(session: Session, execution_id: UUID) -> Execution:
    execution = get_execution(session, execution_id)
    validate_transition(execution.status, ExecutionStatus.CANCELLED)
    result = session.execute(
        update(Execution)
        .where(
            Execution.id == execution_id,
            Execution.status.in_(
                (ExecutionStatus.QUEUED, ExecutionStatus.WAITING_APPROVAL)
            ),
        )
        .values(**_cancellation_values(execution))
    )
    if result.rowcount != 1:
        session.rollback()
        raise ApplicationException(
            "Only queued or approval-waiting executions can be cancelled.",
            status_code=409,
            code="execution_not_cancellable",
        )
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    return get_execution(session, execution_id)


def _cancellation_values(execution: Execution) -> dict[str, object]:
    values: dict[str, object] = {
        "status": ExecutionStatus.CANCELLED,
        "completed_at": datetime.now(timezone.utc),
    }
    if (
        execution.status is ExecutionStatus.WAITING_APPROVAL
        and isinstance(execution.qa_workflow_state, dict)
    ):
        state = dict(execution.qa_workflow_state)
        state.update(
            approval_status=None,
            current_agent="workflow_cancellation",
            workflow_status="CANCELLED",
        )
        values["qa_workflow_state"] = state
    return values
