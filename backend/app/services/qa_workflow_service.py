from datetime import datetime, timezone
import logging
from typing import Any
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.ai.llm_provider import AIProviderError, StructuredOutputProvider
from app.ai.ollama_provider import create_llm_provider
from app.config import get_settings
from app.core.exceptions import ApplicationException
from app.graph.qa_graph import build_qa_graph
from app.graph.qa_state import QAState
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.rag.service import KnowledgeService, create_knowledge_service
from app.schemas.approval import ApprovalDecision
from app.schemas.qa import (
    ApprovalPhase,
    QAApprovalRequest,
    QAWorkflowResponse,
    WorkflowStatus,
)
from app.services.browser_inspection import BrowserInspectionService


_TERMINAL_WORKFLOW_STATES = {
    WorkflowStatus.COMPLETED.value: ExecutionStatus.COMPLETED,
    WorkflowStatus.FAILED.value: ExecutionStatus.FAILED,
    WorkflowStatus.CANCELLED.value: ExecutionStatus.CANCELLED,
}
logger = logging.getLogger(__name__)


def _claim_queued_execution(
    session: Session,
    execution_id: UUID,
) -> tuple[Execution, str]:
    result = session.execute(
        update(Execution)
        .where(
            Execution.id == execution_id,
            Execution.status == ExecutionStatus.QUEUED,
        )
        .values(
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
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
            "A QA workflow can only start for a queued execution.",
            status_code=409,
            code="qa_workflow_not_runnable",
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
    project = session.scalar(
        select(Project).where(Project.id == execution.project_id)
    )
    if project is None:
        raise ApplicationException(
            "Execution project not found.",
            status_code=404,
            code="project_not_found",
        )
    return execution, project.base_url


def _claim_approval(
    session: Session,
    execution_id: UUID,
    request: QAApprovalRequest,
) -> dict[str, Any]:
    execution = session.get(Execution, execution_id)
    if execution is None:
        raise ApplicationException(
            "Execution not found.",
            status_code=404,
            code="execution_not_found",
        )
    if execution.status is not ExecutionStatus.WAITING_APPROVAL:
        raise ApplicationException(
            "This execution is not waiting for QA workflow approval.",
            status_code=409,
            code="qa_approval_not_pending",
        )
    state = execution.qa_workflow_state
    if not isinstance(state, dict) or state.get("approval_status") != "PENDING":
        raise ApplicationException(
            "The saved QA workflow has no pending approval.",
            status_code=409,
            code="qa_approval_not_pending",
        )
    if state.get("approval_phase") not in {
        ApprovalPhase.INSPECTION.value,
        ApprovalPhase.TEST_PLAN.value,
    }:
        raise ApplicationException(
            "The saved QA workflow has an invalid approval stage.",
            status_code=409,
            code="qa_approval_state_invalid",
        )
    result = session.execute(
        update(Execution)
        .where(
            Execution.id == execution_id,
            Execution.status == ExecutionStatus.WAITING_APPROVAL,
        )
        .values(status=ExecutionStatus.RUNNING)
    )
    if result.rowcount != 1:
        session.rollback()
        raise ApplicationException(
            "The QA approval was already handled.",
            status_code=409,
            code="qa_approval_not_pending",
        )
    current_time = datetime.now(timezone.utc).isoformat()
    history = list(state.get("approval_history", []))
    history.append(
        {
            "phase": state.get("approval_phase", ApprovalPhase.INSPECTION.value),
            "decision": request.decision.value,
            "reviewer_comment": request.reviewer_comment,
            "reviewed_at": current_time,
        }
    )
    state.update(
        approval_status=request.decision.value,
        approval_history=history,
        resume_node="check_approval",
        workflow_status=WorkflowStatus.RUNNING.value,
    )
    session.commit()
    return state


def _persist_state(
    session: Session,
    execution_id: UUID,
    state: QAState,
) -> Execution:
    workflow_status = state.get("workflow_status", WorkflowStatus.FAILED.value)
    status = _TERMINAL_WORKFLOW_STATES.get(
        workflow_status,
        ExecutionStatus.WAITING_APPROVAL
        if workflow_status == WorkflowStatus.WAITING_APPROVAL.value
        else ExecutionStatus.RUNNING,
    )
    now = datetime.now(timezone.utc)
    values: dict[str, Any] = {
        "status": status,
        "qa_workflow_state": state,
        "qa_report": state.get("qa_report"),
    }
    if status in {
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    }:
        values["completed_at"] = now
        started_at = session.scalar(
            select(Execution.started_at).where(Execution.id == execution_id)
        )
        if started_at is not None:
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            else:
                started_at = started_at.astimezone(timezone.utc)
            values["duration_ms"] = max(
                0,
                int((now - started_at).total_seconds() * 1000),
            )

    inspection = state.get("website_inspection")
    if inspection is not None:
        values["inspection_result"] = inspection
        values["final_url"] = inspection.get("final_url")
        values["artifact_metadata"] = state.get("inspection_artifacts", [])

    result = session.execute(
        update(Execution)
        .where(
            Execution.id == execution_id,
            Execution.status == ExecutionStatus.RUNNING,
        )
        .values(**values)
    )
    if result.rowcount != 1:
        session.rollback()
        raise ApplicationException(
            "Execution state changed while the QA workflow was running.",
            status_code=409,
            code="qa_execution_state_changed",
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
    return execution


def _response(execution: Execution) -> QAWorkflowResponse:
    state = execution.qa_workflow_state
    if not isinstance(state, dict):
        raise ApplicationException(
            "No QA workflow state has been saved for this execution.",
            status_code=404,
            code="qa_workflow_not_found",
        )
    return QAWorkflowResponse(
        execution_id=execution.id,
        execution_status=execution.status,
        workflow_status=state.get("workflow_status", "FAILED"),
        approval_status=state.get("approval_status"),
        approval_phase=state.get("approval_phase"),
        current_agent=state.get("current_agent"),
        requirement_analysis=state.get("requirement_analysis"),
        testing_plan=state.get("testing_plan"),
        website_understanding=state.get("website_understanding"),
        generated_test_cases=state.get("generated_test_cases", []),
        execution_results=state.get("execution_results", []),
        bug_findings=state.get("bug_findings", []),
        qa_report=state.get("qa_report"),
        rag_status=state.get("rag_status", "not_needed"),
        historical_bug_matches=state.get("historical_bug_matches", []),
        errors=state.get("errors", []),
        warnings=state.get("warnings", []),
        approval_history=state.get("approval_history", []),
    )


def _raise_if_failed(state: QAState) -> None:
    if state.get("workflow_status") != WorkflowStatus.FAILED.value:
        return
    error = (state.get("errors") or [{}])[0]
    code = error.get("code", "qa_workflow_failed")
    message = error.get("message", "The QA workflow failed.")
    status_code = {
        "ai_provider_error": 503,
        "unsafe_target_url": 422,
    }.get(code, 502)
    raise ApplicationException(message, status_code=status_code, code=code)


async def _invoke_graph(
    session: Session,
    execution_id: UUID,
    graph: Any,
    state: QAState,
) -> QAState:
    try:
        return await graph.ainvoke(state)
    except Exception as exc:
        logger.exception(
            "LangGraph execution failed for execution %s (%s)",
            execution_id,
            type(exc).__name__,
        )
        failed_state = dict(state)
        errors = list(failed_state.get("errors", []))
        errors.append(
            {
                "agent": "workflow_engine",
                "code": "qa_graph_failed",
                "message": "The QA workflow engine failed. Check application logs.",
            }
        )
        failed_state.update(
            current_agent="workflow_engine",
            workflow_status=WorkflowStatus.FAILED.value,
            errors=errors,
        )
        await run_in_threadpool(
            _persist_state,
            session,
            execution_id,
            failed_state,
        )
        raise ApplicationException(
            "The QA workflow engine failed. Check application logs.",
            status_code=502,
            code="qa_graph_failed",
        ) from exc


class QAWorkflowService:
    def __init__(
        self,
        inspection_service: BrowserInspectionService,
        provider: StructuredOutputProvider | None = None,
        knowledge_service: KnowledgeService | None = None,
    ) -> None:
        self.inspection_service = inspection_service
        self.provider = provider
        self.knowledge_service = knowledge_service or create_knowledge_service()

    def _provider(self) -> StructuredOutputProvider:
        if self.provider is not None:
            return self.provider
        try:
            return create_llm_provider(get_settings())
        except AIProviderError as exc:
            raise ApplicationException(
                str(exc),
                status_code=503,
                code="ai_provider_error",
            ) from exc

    async def start(
        self,
        session: Session,
        execution_id: UUID,
    ) -> QAWorkflowResponse:
        provider = self._provider()
        execution, target_url = await run_in_threadpool(
            _claim_queued_execution,
            session,
            execution_id,
        )
        state: QAState = {
            "project_id": str(execution.project_id),
            "execution_id": str(execution.id),
            "target_url": target_url,
            "user_requirements": execution.requirements,
            "requirement_analysis": None,
            "testing_plan": None,
            "website_inspection": None,
            "website_understanding": None,
            "generated_test_cases": [],
            "execution_results": [],
            "bug_findings": [],
            "qa_report": None,
            "rag_query": "",
            "retrieved_documents": [],
            "retrieval_metadata": {},
            "historical_bug_matches": [],
            "rag_context": "",
            "rag_status": "not_needed",
            "approval_status": ApprovalDecision.PENDING.value,
            "approval_phase": ApprovalPhase.INSPECTION.value,
            "approval_history": [],
            "current_agent": "requirement_analysis",
            "workflow_status": WorkflowStatus.RUNNING.value,
            "errors": [],
            "warnings": [],
            "evidence_index": {},
            "inspection_artifacts": [],
            "resume_node": None,
        }
        graph = build_qa_graph(
            provider,
            self.inspection_service,
            self.knowledge_service,
        )
        result = await _invoke_graph(session, execution_id, graph, state)
        execution = await run_in_threadpool(
            _persist_state,
            session,
            execution_id,
            result,
        )
        _raise_if_failed(result)
        return _response(execution)

    async def decide(
        self,
        session: Session,
        execution_id: UUID,
        request: QAApprovalRequest,
    ) -> QAWorkflowResponse:
        provider = self._provider()
        state = await run_in_threadpool(
            _claim_approval,
            session,
            execution_id,
            request,
        )
        graph = build_qa_graph(
            provider,
            self.inspection_service,
            self.knowledge_service,
        )
        result = await _invoke_graph(session, execution_id, graph, state)
        execution = await run_in_threadpool(
            _persist_state,
            session,
            execution_id,
            result,
        )
        _raise_if_failed(result)
        return _response(execution)

    async def get(
        self,
        session: Session,
        execution_id: UUID,
    ) -> QAWorkflowResponse:
        execution = await run_in_threadpool(session.get, Execution, execution_id)
        if execution is None:
            raise ApplicationException(
                "Execution not found.",
                status_code=404,
                code="execution_not_found",
            )
        return _response(execution)
