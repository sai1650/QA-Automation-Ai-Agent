from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.approval import Approval, ApprovalDecision
from app.schemas.execution import ExecutionCreate, ExecutionResponse, ExecutionStatus
from app.schemas.finding import Finding, FindingStatus, Severity
from app.schemas.project import ProjectCreate, ProjectResponse
from app.schemas.report import Report
from app.schemas.test_case import TestCase as CaseSchema
from app.schemas.test_case import TestCasePriority as CasePriority


def test_valid_project_create() -> None:
    project = ProjectCreate(
        name="  Example  ",
        base_url="https://example.com",
        authorization_confirmed=True,
    )

    assert project.name == "Example"
    assert str(project.base_url) == "https://example.com/"


def test_project_response_serializes_uuid_and_timestamps() -> None:
    project_id = uuid4()
    timestamp = datetime.now(timezone.utc)
    project = ProjectResponse(
        id=project_id,
        name="Example",
        base_url="https://example.com",
        description=None,
        is_active=True,
        created_at=timestamp,
        updated_at=timestamp,
    )

    payload = project.model_dump(mode="json")

    assert payload["id"] == str(project_id)
    assert payload["created_at"] == timestamp.isoformat().replace("+00:00", "Z")


@pytest.mark.parametrize("name", ["", "   "])
def test_invalid_project_name(name: str) -> None:
    with pytest.raises(ValidationError):
        ProjectCreate(
            name=name,
            base_url="https://example.com",
            authorization_confirmed=True,
        )


def test_invalid_project_url() -> None:
    with pytest.raises(ValidationError):
        ProjectCreate(
            name="Example",
            base_url="ftp://example.com",
            authorization_confirmed=True,
        )


def test_missing_project_authorization_confirmation() -> None:
    with pytest.raises(ValidationError):
        ProjectCreate(name="Example", base_url="https://example.com")


def test_project_authorization_must_be_confirmed() -> None:
    with pytest.raises(ValidationError):
        ProjectCreate(
            name="Example",
            base_url="https://example.com",
            authorization_confirmed=False,
        )


def test_valid_execution_create() -> None:
    execution = ExecutionCreate(
        project_id=uuid4(),
        requirements="Verify that the landing page loads.",
        authorized_target_confirmation=True,
    )

    assert execution.requirements == "Verify that the landing page loads."
    assert execution.options is None


def test_invalid_execution_status() -> None:
    with pytest.raises(ValidationError):
        ExecutionResponse(
            id=uuid4(),
            project_id=uuid4(),
            status="UNKNOWN",
            requirements="Test requirements",
            options={},
            created_at=datetime.now(timezone.utc),
            started_at=None,
            completed_at=None,
        )


def test_valid_finding_schema() -> None:
    finding = Finding(
        id=uuid4(),
        execution_id=uuid4(),
        title="Broken link",
        description="The link returns a not found response.",
        severity=Severity.MEDIUM,
        status=FindingStatus.OPEN,
        reproduction_steps=["Open the landing page", "Select the help link"],
        expected_result="The help page loads.",
        actual_result="The server returns 404.",
        created_at=datetime.now(timezone.utc),
    )

    assert finding.severity is Severity.MEDIUM


def test_invalid_severity() -> None:
    with pytest.raises(ValidationError):
        Finding(
            id=uuid4(),
            execution_id=uuid4(),
            title="Broken link",
            description="The link returns a not found response.",
            severity="URGENT",
            status=FindingStatus.OPEN,
            reproduction_steps=["Open the page"],
            expected_result="The page loads.",
            actual_result="The server returns 404.",
            created_at=datetime.now(timezone.utc),
        )


def test_valid_approval_schema() -> None:
    approval = Approval(
        id=uuid4(),
        execution_id=uuid4(),
        action_description="Submit the pre-approved test form.",
        decision=ApprovalDecision.PENDING,
        created_at=datetime.now(timezone.utc),
        reviewed_at=None,
    )

    assert approval.decision is ApprovalDecision.PENDING
    assert approval.model_dump(mode="json")["decision"] == "PENDING"


def test_test_case_uses_validated_steps() -> None:
    test_case = CaseSchema(
        id=uuid4(),
        title="Successful sign-in",
        description="A registered user can sign in.",
        steps=[{"order": 1, "action": "Enter valid credentials"}],
        expected_result="The account page is displayed.",
        priority=CasePriority.P1,
        category="authentication",
    )

    assert test_case.steps[0].order == 1
    assert test_case.steps[0].action == "Enter valid credentials"


def test_report_rejects_negative_counts() -> None:
    with pytest.raises(ValidationError):
        Report(
            id=uuid4(),
            execution_id=uuid4(),
            total_tests=-1,
            passed_tests=0,
            failed_tests=0,
            skipped_tests=0,
            findings_count=0,
            summary="No tests were run.",
            generated_at=datetime.now(timezone.utc),
        )
