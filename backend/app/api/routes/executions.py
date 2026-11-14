from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.dependencies import (
    get_browser_inspection_service,
    get_qa_workflow_service,
)
from app.database.session import get_db
from app.models.execution import ExecutionStatus
from app.schemas.execution import (
    ExecutionCreate,
    ExecutionArtifactsResponse,
    ExecutionListResponse,
    InspectionResponse,
    ExecutionResponse,
)
from app.schemas.qa import QAApprovalRequest, QAWorkflowResponse
from app.services import execution_service
from app.services.browser_execution_service import run_execution_inspection
from app.services.browser_inspection import BrowserInspectionService
from app.services.qa_workflow_service import QAWorkflowService
from app.services.execution_service import SortOrder

router = APIRouter()


@router.post(
    "/projects/{project_id}/executions",
    response_model=ExecutionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Queue an execution",
    description=(
        "Persists a queued execution only. This endpoint does not start agents, "
        "browser automation, or background workers."
    ),
    responses={
        201: {
            "description": "Execution record created in the queued state.",
            "content": {
                "application/json": {
                    "example": {
                        "id": "9bb0c235-233f-455e-a701-03fdf165fd60",
                        "project_id": "8e39e85a-5356-4833-becf-a7cc6d5aa920",
                        "status": "QUEUED",
                        "requirements": "Test login and product search.",
                        "options": {"browser": "chromium"},
                        "created_at": "2026-11-09T12:00:00Z",
                        "started_at": None,
                        "completed_at": None,
                    }
                }
            },
        },
        404: {"description": "Project not found."},
        409: {"description": "Project is archived."},
        422: {"description": "Invalid execution data or confirmation missing."},
    },
)
def create_execution(
    project_id: UUID,
    payload: Annotated[
        ExecutionCreate,
        Body(
            openapi_examples={
                "queued_execution": {
                    "summary": "Queue an authorized execution",
                    "value": {
                        "requirements": "Test login, registration and product search.",
                        "options": {
                            "browser": "chromium",
                            "capture_screenshots": True,
                        },
                        "authorized_target_confirmation": True,
                    },
                }
            }
        ),
    ],
    session: Session = Depends(get_db),
) -> ExecutionResponse:
    return execution_service.create_execution(session, project_id, payload)


@router.get(
    "/executions",
    response_model=ExecutionListResponse,
    summary="List executions",
    responses={
        422: {"description": "Invalid project ID, pagination, status, or sort order."}
    },
)
def list_executions(
    session: Session = Depends(get_db),
    project_id: UUID | None = None,
    execution_status: Annotated[
        ExecutionStatus | None, Query(alias="status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    skip: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    sort_order: SortOrder = SortOrder.DESC,
) -> ExecutionListResponse:
    offset = skip if skip is not None else (page - 1) * page_size
    effective_limit = limit if limit is not None else page_size
    items, total = execution_service.list_executions(
        session,
        project_id=project_id,
        status=execution_status,
        offset=offset,
        limit=effective_limit,
        sort_order=sort_order,
    )
    return ExecutionListResponse(
        items=items,
        total=total,
        page=offset // effective_limit + 1,
        page_size=effective_limit,
        skip=offset,
        limit=effective_limit,
    )


@router.get(
    "/projects/{project_id}/executions",
    response_model=ExecutionListResponse,
    summary="List executions for a project",
    responses={
        404: {"description": "Project not found."},
        422: {"description": "Invalid pagination, status, or sort parameters."},
    },
)
def list_project_executions(
    project_id: UUID,
    session: Session = Depends(get_db),
    execution_status: Annotated[
        ExecutionStatus | None, Query(alias="status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    skip: Annotated[int | None, Query(ge=0)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    sort_order: SortOrder = SortOrder.DESC,
) -> ExecutionListResponse:
    offset = skip if skip is not None else (page - 1) * page_size
    effective_limit = limit if limit is not None else page_size
    items, total = execution_service.list_project_executions(
        session,
        project_id,
        status=execution_status,
        offset=offset,
        limit=effective_limit,
        sort_order=sort_order,
    )
    return ExecutionListResponse(
        items=items,
        total=total,
        page=offset // effective_limit + 1,
        page_size=effective_limit,
        skip=offset,
        limit=effective_limit,
    )


@router.get(
    "/executions/{execution_id}",
    response_model=ExecutionResponse,
    summary="Get an execution",
    responses={404: {"description": "Execution not found."}},
)
def get_execution(
    execution_id: UUID,
    session: Session = Depends(get_db),
) -> ExecutionResponse:
    return execution_service.get_execution(session, execution_id)


@router.post(
    "/executions/{execution_id}/cancel",
    response_model=ExecutionResponse,
    summary="Cancel a queued or approval-waiting execution",
    description=(
        "Cancels an execution that has not passed the pending human-approval gate."
    ),
    responses={
        404: {"description": "Execution not found."},
        409: {"description": "Execution is running or already terminal."},
    },
)
def cancel_execution(
    execution_id: UUID,
    session: Session = Depends(get_db),
) -> ExecutionResponse:
    return execution_service.cancel_execution(session, execution_id)


@router.post(
    "/executions/{execution_id}/run",
    response_model=InspectionResponse,
    summary="Run browser inspection",
    description=(
        "Runs an authorized, read-only browser inspection for a queued execution. "
        "Execution creation itself never launches a browser."
    ),
    responses={
        404: {"description": "Execution not found."},
        409: {"description": "Execution is not queued."},
        422: {"description": "Target URL failed network safety validation."},
        502: {"description": "Browser inspection failed."},
    },
)
async def run_browser_inspection(
    execution_id: UUID,
    session: Session = Depends(get_db),
    inspection_service: BrowserInspectionService = Depends(
        get_browser_inspection_service
    ),
) -> InspectionResponse:
    return await run_execution_inspection(
        session,
        execution_id,
        inspection_service,
    )


@router.get(
    "/executions/{execution_id}/inspection",
    response_model=InspectionResponse,
    summary="Get browser inspection result",
    responses={404: {"description": "Execution not found."}},
)
async def get_browser_inspection(
    execution_id: UUID,
    session: Session = Depends(get_db),
) -> InspectionResponse:
    execution = await run_in_threadpool(
        execution_service.get_execution,
        session,
        execution_id,
    )
    return InspectionResponse(
        execution_id=execution.id,
        status=execution.status,
        duration_ms=execution.duration_ms,
        final_url=execution.final_url,
        result=execution.inspection_result,
    )


@router.get(
    "/executions/{execution_id}/artifacts",
    response_model=ExecutionArtifactsResponse,
    summary="Get inspection artifact metadata",
    description=(
        "Returns metadata for artifacts owned by this execution. Local filesystem "
        "paths and arbitrary file access are never exposed."
    ),
    responses={404: {"description": "Execution not found."}},
)
async def get_execution_artifacts(
    execution_id: UUID,
    session: Session = Depends(get_db),
) -> ExecutionArtifactsResponse:
    execution = await run_in_threadpool(
        execution_service.get_execution,
        session,
        execution_id,
    )
    return ExecutionArtifactsResponse(
        execution_id=execution.id,
        items=execution.artifact_metadata or [],
    )


@router.post(
    "/executions/{execution_id}/qa-workflow",
    response_model=QAWorkflowResponse,
    status_code=status.HTTP_200_OK,
    summary="Start the multi-agent QA workflow",
    description=(
        "Analyzes requirements and plans tests, then pauses for approval before "
        "read-only browser inspection. A second approval is required before "
        "generated tests are coordinated."
    ),
    responses={
        404: {"description": "Execution not found."},
        409: {"description": "Execution is not queued."},
        422: {"description": "Target failed URL safety validation."},
        502: {"description": "An agent or browser inspection failed."},
        503: {"description": "Ollama is unavailable or not configured."},
    },
)
async def start_qa_workflow(
    execution_id: UUID,
    session: Session = Depends(get_db),
    workflow: QAWorkflowService = Depends(get_qa_workflow_service),
) -> QAWorkflowResponse:
    return await workflow.start(session, execution_id)


@router.post(
    "/executions/{execution_id}/qa-workflow/approval",
    response_model=QAWorkflowResponse,
    summary="Approve or reject the pending QA workflow stage",
    description=(
        "The first approval authorizes the existing read-only browser inspection. "
        "The second approval reviews the generated test plan before coordination."
    ),
    responses={
        404: {"description": "Execution not found."},
        409: {"description": "No approval is currently pending."},
        502: {"description": "An agent or browser inspection failed."},
        503: {"description": "Ollama is unavailable or not configured."},
    },
)
async def decide_qa_workflow_approval(
    execution_id: UUID,
    payload: QAApprovalRequest,
    session: Session = Depends(get_db),
    workflow: QAWorkflowService = Depends(get_qa_workflow_service),
) -> QAWorkflowResponse:
    return await workflow.decide(session, execution_id, payload)


@router.get(
    "/executions/{execution_id}/qa-workflow",
    response_model=QAWorkflowResponse,
    summary="Get persisted QA workflow state and report",
    responses={
        404: {"description": "Execution or QA workflow not found."},
    },
)
async def get_qa_workflow(
    execution_id: UUID,
    session: Session = Depends(get_db),
    workflow: QAWorkflowService = Depends(get_qa_workflow_service),
) -> QAWorkflowResponse:
    return await workflow.get(session, execution_id)
