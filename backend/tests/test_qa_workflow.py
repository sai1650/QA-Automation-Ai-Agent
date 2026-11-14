import asyncio
from typing import Any
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.ai.llm_provider import AIProviderError
from app.dependencies import get_qa_workflow_service
from app.main import app
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.schemas.approval import ApprovalDecision
from app.schemas.qa import (
    ApprovalPhase,
    BugFindingSet,
    QAApprovalRequest,
    ReportNarrative,
    RequirementAnalysis,
    TestCasePriority as Priority,
    TestCaseSet as CasesSchema,
    TestType as QAType,
    TestingPlan as PlanSchema,
    ValidationKind,
    WebsiteUnderstanding,
)
from app.services.qa_workflow_service import QAWorkflowService
from tests.test_projects import create_project


class FakeProvider:
    def __init__(self, *, failure: Exception | None = None) -> None:
        self.failure = failure
        self.calls: list[str] = []
        self.prompts: list[str] = []

    async def generate(self, prompt: str, schema: type[Any]) -> Any:
        self.calls.append(schema.__name__)
        self.prompts.append(prompt)
        if self.failure is not None:
            raise self.failure
        if schema is RequirementAnalysis:
            return RequirementAnalysis(
                objectives=["Verify the requested home-page behavior."],
                functional_requirements=[
                    {
                        "requirement_id": "REQ-01",
                        "description": "Load the home page and inspect its controls.",
                        "expected_behavior": "The page loads and a control is present.",
                    }
                ],
                constraints=["Read-only inspection only."],
            )
        if schema is PlanSchema:
            return PlanSchema(
                tasks=[
                    {
                        "test_id": "TASK-01",
                        "objective": "Inspect the home page.",
                        "requirement_ref": "REQ-01",
                        "priority": Priority.P1,
                        "prerequisites": [],
                        "risk": "The page may not load.",
                        "expected_outcome": "The page loads.",
                        "required_evidence": ["HTTP navigation status"],
                    }
                ]
            )
        if schema is WebsiteUnderstanding:
            return WebsiteUnderstanding(
                summary="The inspected page contains one observed button.",
                requirement_evidence=[
                    {
                        "requirement_id": "REQ-01",
                        "support": "SUPPORTED",
                        "evidence_references": ["page.title"],
                        "missing_evidence": [],
                    }
                ],
                observed_element_references=["elements.buttons[0]"],
            )
        if schema is CasesSchema:
            return CasesSchema(
                test_cases=[
                    {
                        "test_case_id": "TC-01",
                        "title": "Check the home page loads",
                        "requirement_id": "REQ-01",
                        "description": "Observe the page load result.",
                        "preconditions": [],
                        "steps": ["Open the authorized home page."],
                        "expected_result": "The page loads successfully.",
                        "priority": Priority.P1,
                        "test_type": QAType.PAGE_LOAD,
                        "evidence_requirements": ["page.navigation_status"],
                        "validation_criteria": {
                            "kind": ValidationKind.PAGE_LOAD,
                        },
                    },
                    {
                        "test_case_id": "TC-02",
                        "title": "Submit a form",
                        "requirement_id": "REQ-01",
                        "description": "Submit a form on the page.",
                        "preconditions": [],
                        "steps": ["Fill and submit the form."],
                        "expected_result": "The form is submitted.",
                        "priority": Priority.P2,
                        "test_type": QAType.INTERACTION,
                        "evidence_requirements": ["elements.forms.count"],
                        "validation_criteria": {
                            "kind": ValidationKind.UNSUPPORTED,
                        },
                    },
                ]
            )
        if schema is BugFindingSet:
            return BugFindingSet(findings=[])
        if schema is ReportNarrative:
            return ReportNarrative(
                summary="One read-only page-load test passed; one interaction was unsupported.",
                recommendations=["Manually validate the unsupported form interaction."],
            )
        raise AssertionError(f"Unexpected structured-output schema: {schema.__name__}")


class FakeInspectionService:
    def __init__(self) -> None:
        self.calls = 0
        self.last_artifacts: list[dict[str, Any]] = [
            {"name": "inspection/page_metadata.json", "media_type": "application/json", "size_bytes": 100}
        ]
        self.settings = SimpleNamespace(browser_execution_timeout_ms=60_000)
        self.last_call: tuple[Any, str] | None = None

    async def inspect(self, execution_id: Any, target_url: str) -> dict[str, Any]:
        self.calls += 1
        self.last_call = (execution_id, target_url)
        return {
            "final_url": "https://example.com/",
            "navigation_status": 200,
            "page_load_status": "load",
            "title": "Example",
            "interactive_elements": {
                "buttons": [{"tag": "button"}],
                "links": [],
                "inputs": [],
                "selects": [],
                "textareas": [],
                "forms": [],
                "total_count": 1,
                "truncated": False,
            },
            "events": {"console": [], "page_errors": [], "network": []},
        }


def _create_execution(session: Session) -> Execution:
    project = Project(name="QA workflow test", base_url="https://example.com/")
    execution = Execution(
        project=project,
        status=ExecutionStatus.QUEUED,
        requirements="Verify that the home page loads and has a button.",
    )
    session.add(execution)
    session.commit()
    session.refresh(execution)
    return execution


def test_qa_workflow_pauses_twice_and_persists_report(db_session: Session) -> None:
    execution = _create_execution(db_session)
    provider = FakeProvider()
    inspection = FakeInspectionService()
    service = QAWorkflowService(inspection, provider)

    initial = asyncio.run(service.start(db_session, execution.id))
    assert initial.workflow_status.value == "WAITING_APPROVAL"
    assert initial.approval_phase is ApprovalPhase.INSPECTION
    assert initial.execution_status.value == ExecutionStatus.WAITING_APPROVAL.value
    assert inspection.calls == 0

    test_approval = asyncio.run(
        service.decide(
            db_session,
            execution.id,
            QAApprovalRequest(decision=ApprovalDecision.APPROVED),
        )
    )
    assert test_approval.workflow_status.value == "WAITING_APPROVAL"
    assert test_approval.approval_phase is ApprovalPhase.TEST_PLAN
    assert len(test_approval.generated_test_cases) == 2
    assert inspection.calls == 1
    assert inspection.last_call is not None
    assert inspection.last_call[1] == "https://example.com/"

    completed = asyncio.run(
        service.decide(
            db_session,
            execution.id,
            QAApprovalRequest(decision=ApprovalDecision.APPROVED),
        )
    )
    assert completed.workflow_status.value == "COMPLETED"
    assert completed.execution_status.value == ExecutionStatus.COMPLETED.value
    assert [item.status.value for item in completed.execution_results] == [
        "PASSED",
        "NOT_SUPPORTED",
    ]
    assert completed.qa_report is not None
    assert completed.qa_report.status_counts["PASSED"] == 1
    assert completed.qa_report.status_counts["NOT_SUPPORTED"] == 1
    assert completed.approval_history[0]["phase"] == "INSPECTION"
    assert completed.approval_history[1]["phase"] == "TEST_PLAN"

    db_session.expire_all()
    persisted = db_session.get(Execution, execution.id)
    assert persisted is not None
    assert persisted.qa_workflow_state is not None
    assert persisted.qa_report is not None
    assert persisted.inspection_result is not None
    assert persisted.artifact_metadata == inspection.last_artifacts


def test_rejected_inspection_approval_cancels_without_browser_access(
    db_session: Session,
) -> None:
    execution = _create_execution(db_session)
    inspection = FakeInspectionService()
    service = QAWorkflowService(inspection, FakeProvider())
    asyncio.run(service.start(db_session, execution.id))

    rejected = asyncio.run(
        service.decide(
            db_session,
            execution.id,
            QAApprovalRequest(
                decision=ApprovalDecision.REJECTED,
                reviewer_comment="Do not inspect this target.",
            ),
        )
    )

    assert rejected.workflow_status.value == "CANCELLED"
    assert rejected.execution_status.value == ExecutionStatus.CANCELLED.value
    assert inspection.calls == 0
    assert rejected.approval_history[0]["reviewer_comment"] == (
        "Do not inspect this target."
    )


def test_ollama_failure_is_actionable_and_persisted(db_session: Session) -> None:
    execution = _create_execution(db_session)
    provider = FakeProvider(
        failure=AIProviderError(
            "Ollama is unavailable. Check OLLAMA_BASE_URL and OLLAMA_MODEL."
        )
    )
    service = QAWorkflowService(FakeInspectionService(), provider)

    from app.core.exceptions import ApplicationException

    with pytest.raises(ApplicationException) as exc_info:
        asyncio.run(service.start(db_session, execution.id))

    assert exc_info.value.status_code == 503
    assert "Ollama is unavailable" in exc_info.value.message
    db_session.expire_all()
    persisted = db_session.get(Execution, execution.id)
    assert persisted is not None
    assert persisted.status is ExecutionStatus.FAILED
    assert persisted.qa_workflow_state["errors"][0]["code"] == "ai_provider_error"


def test_qa_workflow_http_routes_start_and_return_persisted_state(
    client: Any,
) -> None:
    project = create_project(client, name="QA API workflow")
    execution_data = client.post(
        f"/api/v1/projects/{project['id']}/executions",
        json={
            "requirements": "Verify the home page loads.",
            "authorized_target_confirmation": True,
        },
    ).json()
    workflow_service = QAWorkflowService(
        FakeInspectionService(),
        FakeProvider(),
    )
    app.dependency_overrides[get_qa_workflow_service] = lambda: workflow_service
    try:
        workflow_url = (
            f"/api/v1/executions/{execution_data['id']}/qa-workflow"
        )
        started = client.post(workflow_url)
        assert started.status_code == 200
        assert started.json()["workflow_status"] == "WAITING_APPROVAL"
        assert started.json()["approval_phase"] == "INSPECTION"

        persisted = client.get(workflow_url)
        assert persisted.status_code == 200
        assert persisted.json()["execution_status"] == "WAITING_APPROVAL"
    finally:
        app.dependency_overrides.pop(get_qa_workflow_service, None)
