import logging
import time
import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationException
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.schemas.execution import InspectionResponse
from app.services.browser_inspection import (
    BrowserInspectionFailure,
    BrowserInspectionService,
)

logger = logging.getLogger(__name__)


def _claim_queued_execution(session: Session, execution_id: UUID) -> str:
    result = session.execute(
        update(Execution)
        .where(
            Execution.id == execution_id,
            Execution.status == ExecutionStatus.QUEUED,
        )
        .values(status=ExecutionStatus.RUNNING, started_at=datetime.now(timezone.utc))
    )
    if result.rowcount != 1:
        session.rollback()
        execution = session.get(Execution, execution_id)
        if execution is None:
            raise ApplicationException(
                "Execution not found.",
                status_code=404,
                code="execution_not_found",
            )
        raise ApplicationException(
            "Execution can only be run while queued.",
            status_code=409,
            code="execution_not_runnable",
        )
    session.commit()
    session.expire_all()
    execution = session.get(Execution, execution_id)
    if execution is None:
        raise ApplicationException(
            "Execution not found.",
            status_code=404,
            code="execution_not_found",
        )
    project = session.get(Project, execution.project_id)
    if project is None:
        raise ApplicationException(
            "Execution project not found.",
            status_code=404,
            code="project_not_found",
        )
    return project.base_url


def _finish_execution(
    session: Session,
    execution_id: UUID,
    *,
    status: ExecutionStatus,
    duration_ms: int,
    final_url: str | None,
    inspection_result: dict[str, Any],
    artifact_metadata: list[dict[str, Any]],
) -> Execution:
    result = session.execute(
        update(Execution)
        .where(
            Execution.id == execution_id,
            Execution.status == ExecutionStatus.RUNNING,
        )
        .values(
            status=status,
            completed_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
            final_url=final_url,
            inspection_result=inspection_result,
            artifact_metadata=artifact_metadata,
        )
    )
    if result.rowcount != 1:
        session.rollback()
        raise RuntimeError("Execution state changed before inspection completed.")
    session.commit()
    session.expire_all()
    execution = session.get(Execution, execution_id)
    if execution is None:
        raise RuntimeError("Execution disappeared after inspection completed.")
    return execution


async def run_execution_inspection(
    session: Session,
    execution_id: UUID,
    inspection_service: BrowserInspectionService,
) -> InspectionResponse:
    target_url = await run_in_threadpool(
        _claim_queued_execution,
        session,
        execution_id,
    )
    started = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            inspection_service.inspect(execution_id, target_url),
            timeout=inspection_service.settings.browser_execution_timeout_ms / 1000,
        )
    except BrowserInspectionFailure as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        await run_in_threadpool(
            _finish_execution,
            session,
            execution_id,
            status=ExecutionStatus.FAILED,
            duration_ms=duration_ms,
            final_url=exc.result.get("final_url"),
            inspection_result=exc.result,
            artifact_metadata=exc.artifacts,
        )
        raise ApplicationException(
            str(exc),
            status_code=exc.status_code,
            code=exc.code,
        ) from exc
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        failure = {
            "error": "Browser inspection failed.",
            "failure_type": type(exc).__name__,
        }
        await run_in_threadpool(
            _finish_execution,
            session,
            execution_id,
            status=ExecutionStatus.FAILED,
            duration_ms=duration_ms,
            final_url=None,
            inspection_result=failure,
            artifact_metadata=[],
        )
        logger.error("Browser inspection failed: %s", type(exc).__name__)
        raise ApplicationException(
            "Browser inspection failed.",
            status_code=502,
            code="browser_inspection_failed",
        ) from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    execution = await run_in_threadpool(
        _finish_execution,
        session,
        execution_id,
        status=ExecutionStatus.COMPLETED,
        duration_ms=duration_ms,
        final_url=result.get("final_url"),
        inspection_result=result,
        artifact_metadata=inspection_service.last_artifacts,
    )
    return InspectionResponse(
        execution_id=execution.id,
        status=execution.status,
        duration_ms=execution.duration_ms,
        final_url=execution.final_url,
        result=execution.inspection_result,
    )
