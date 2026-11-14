from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common import CommonSchema
from app.schemas.approval import ApprovalDecision
from app.schemas.execution import ExecutionStatus
from app.schemas.finding import Severity
from app.schemas.test_case import TestCasePriority


class TestType(str, Enum):
    PAGE_LOAD = "PAGE_LOAD"
    ELEMENT_PRESENCE = "ELEMENT_PRESENCE"
    INTERACTION = "INTERACTION"
    API = "API"
    OTHER = "OTHER"


class ValidationKind(str, Enum):
    PAGE_LOAD = "PAGE_LOAD"
    ELEMENT_COUNT = "ELEMENT_COUNT"
    UNSUPPORTED = "UNSUPPORTED"


class ElementKind(str, Enum):
    BUTTON = "BUTTON"
    LINK = "LINK"
    INPUT = "INPUT"
    SELECT = "SELECT"
    TEXTAREA = "TEXTAREA"
    FORM = "FORM"


class TestOutcome(str, Enum):
    EXECUTED = "EXECUTED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    SKIPPED = "SKIPPED"


class ApprovalPhase(str, Enum):
    INSPECTION = "INSPECTION"
    TEST_PLAN = "TEST_PLAN"


class WorkflowStatus(str, Enum):
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Requirement(CommonSchema):
    requirement_id: str = Field(pattern=r"^REQ-[0-9]{2,4}$")
    description: str = Field(min_length=1, max_length=2000)
    expected_behavior: str | None = Field(default=None, max_length=2000)


class RequirementAnalysis(CommonSchema):
    objectives: list[str] = Field(min_length=1, max_length=30)
    functional_requirements: list[Requirement] = Field(min_length=1, max_length=50)
    constraints: list[str] = Field(default_factory=list, max_length=50)
    limitations: list[str] = Field(default_factory=list, max_length=50)
    ambiguities: list[str] = Field(default_factory=list, max_length=50)
    missing_information: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def requirement_ids_are_unique(self) -> "RequirementAnalysis":
        ids = [item.requirement_id for item in self.functional_requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("Requirement IDs must be unique.")
        return self


class PlannedTask(CommonSchema):
    test_id: str = Field(pattern=r"^TASK-[0-9]{2,4}$")
    objective: str = Field(min_length=1, max_length=1000)
    requirement_ref: str = Field(pattern=r"^REQ-[0-9]{2,4}$")
    priority: TestCasePriority
    prerequisites: list[str] = Field(default_factory=list, max_length=30)
    risk: str = Field(min_length=1, max_length=1000)
    expected_outcome: str = Field(min_length=1, max_length=1000)
    required_evidence: list[str] = Field(min_length=1, max_length=30)


class TestingPlan(CommonSchema):
    tasks: list[PlannedTask] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def task_ids_and_references_are_valid(self) -> "TestingPlan":
        task_ids = [task.test_id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("Plan task identifiers must be unique.")
        task_positions = {
            task.test_id: index for index, task in enumerate(self.tasks)
        }
        for index, task in enumerate(self.tasks):
            if any(
                item not in task_positions or task_positions[item] >= index
                for item in task.prerequisites
            ):
                raise ValueError(
                    "Plan prerequisites must reference earlier tasks."
                )
        return self


class RequirementEvidence(CommonSchema):
    requirement_id: str = Field(pattern=r"^REQ-[0-9]{2,4}$")
    support: str = Field(pattern=r"^(SUPPORTED|PARTIAL|NOT_OBSERVED)$")
    evidence_references: list[str] = Field(default_factory=list, max_length=50)
    missing_evidence: list[str] = Field(default_factory=list, max_length=30)


class WebsiteUnderstanding(CommonSchema):
    summary: str = Field(min_length=1, max_length=3000)
    requirement_evidence: list[RequirementEvidence] = Field(
        default_factory=list,
        max_length=50,
    )
    observed_element_references: list[str] = Field(
        default_factory=list,
        max_length=250,
    )


class TestValidation(CommonSchema):
    kind: ValidationKind
    element_kind: ElementKind | None = None
    minimum_count: int | None = Field(default=None, ge=1, le=250)

    @model_validator(mode="after")
    def validation_parameters_match_kind(self) -> "TestValidation":
        if self.kind is ValidationKind.ELEMENT_COUNT:
            if self.element_kind is None or self.minimum_count is None:
                raise ValueError(
                    "ELEMENT_COUNT requires an element_kind and minimum_count."
                )
        elif self.element_kind is not None or self.minimum_count is not None:
            raise ValueError(
                "Only ELEMENT_COUNT may specify element validation parameters."
            )
        return self


class GeneratedTestCase(CommonSchema):
    test_case_id: str = Field(pattern=r"^TC-[0-9]{2,4}$")
    title: str = Field(min_length=1, max_length=200)
    requirement_id: str = Field(pattern=r"^REQ-[0-9]{2,4}$")
    description: str = Field(min_length=1, max_length=2000)
    preconditions: list[str] = Field(default_factory=list, max_length=30)
    steps: list[str] = Field(min_length=1, max_length=30)
    expected_result: str = Field(min_length=1, max_length=2000)
    priority: TestCasePriority
    test_type: TestType
    evidence_requirements: list[str] = Field(default_factory=list, max_length=30)
    validation_criteria: TestValidation
    depends_on: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("steps")
    @classmethod
    def steps_must_not_be_blank(cls, value: list[str]) -> list[str]:
        normalized = [step.strip() for step in value]
        if any(not step for step in normalized):
            raise ValueError("Test steps must not be blank.")
        return normalized


class TestCaseSet(CommonSchema):
    test_cases: list[GeneratedTestCase] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def test_case_ids_and_dependencies_are_valid(self) -> "TestCaseSet":
        identifiers = [case.test_case_id for case in self.test_cases]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Test-case identifiers must be unique.")
        positions = {
            case.test_case_id: index
            for index, case in enumerate(self.test_cases)
        }
        for index, case in enumerate(self.test_cases):
            if any(
                dependency not in positions or positions[dependency] >= index
                for dependency in case.depends_on
            ):
                raise ValueError(
                    "Test dependencies must reference earlier test cases."
                )
        return self


class ExecutionResult(CommonSchema):
    test_case_id: str
    status: TestOutcome
    summary: str = Field(min_length=1, max_length=2000)
    actual_result: str | None = Field(default=None, max_length=2000)
    evidence_references: list[str] = Field(default_factory=list, max_length=50)
    unsupported_reason: str | None = Field(default=None, max_length=1000)


class BugFinding(CommonSchema):
    bug_id: str = Field(pattern=r"^BUG-[0-9]{2,4}$")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=3000)
    severity: Severity
    confidence_score: float = Field(ge=0, le=1)
    probable_root_cause: str = Field(min_length=1, max_length=2000)
    supporting_evidence: list[str] = Field(min_length=1, max_length=50)
    affected_url: str | None = Field(default=None, max_length=2048)
    recommended_action: str = Field(min_length=1, max_length=2000)
    historical_references: list[str] = Field(default_factory=list, max_length=20)


class BugFindingSet(CommonSchema):
    findings: list[BugFinding] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def bug_ids_are_unique(self) -> "BugFindingSet":
        ids = [finding.bug_id for finding in self.findings]
        if len(ids) != len(set(ids)):
            raise ValueError("Bug identifiers must be unique.")
        return self


class ReportNarrative(CommonSchema):
    summary: str = Field(min_length=1, max_length=5000)
    recommendations: list[str] = Field(default_factory=list, max_length=30)


class ReportFact(CommonSchema):
    fact: str = Field(min_length=1, max_length=1000)
    evidence_references: list[str] = Field(min_length=1, max_length=30)


class HistoricalBugMatch(CommonSchema):
    document_id: str
    title: str
    source_reference: str
    similarity_score: float
    severity: str | None = None
    execution_id: UUID | None = None
    match_type: Literal["similar_historical_issue"] = "similar_historical_issue"


class QAReport(CommonSchema):
    execution_id: UUID
    generated_at: datetime
    summary: str = Field(min_length=1, max_length=5000)
    status_counts: dict[TestOutcome, int]
    tests: list[GeneratedTestCase]
    execution_results: list[ExecutionResult]
    findings: list[BugFinding]
    observed_facts: list[ReportFact]
    ai_analysis: list[str]
    recommendations: list[str]
    rag_status: str = "not_needed"
    historical_bug_matches: list[HistoricalBugMatch] = Field(default_factory=list)

    @model_validator(mode="after")
    def counts_match_execution_results(self) -> "QAReport":
        actual = {status: 0 for status in TestOutcome}
        for result in self.execution_results:
            actual[result.status] += 1
        if self.status_counts != actual:
            raise ValueError("Report counts must match the execution results.")
        return self


class QAApprovalRequest(CommonSchema):
    decision: ApprovalDecision
    reviewer_comment: str | None = Field(default=None, max_length=2000)

    @field_validator("decision")
    @classmethod
    def approval_decision_must_be_final(
        cls, value: ApprovalDecision
    ) -> ApprovalDecision:
        if value is ApprovalDecision.PENDING:
            raise ValueError("An approval decision must be APPROVED or REJECTED.")
        return value


class QAWorkflowResponse(CommonSchema):
    execution_id: UUID
    execution_status: ExecutionStatus
    workflow_status: WorkflowStatus
    approval_status: ApprovalDecision | None = None
    approval_phase: ApprovalPhase | None = None
    current_agent: str | None = None
    requirement_analysis: RequirementAnalysis | None = None
    testing_plan: TestingPlan | None = None
    website_understanding: WebsiteUnderstanding | None = None
    generated_test_cases: list[GeneratedTestCase] = Field(default_factory=list)
    execution_results: list[ExecutionResult] = Field(default_factory=list)
    bug_findings: list[BugFinding] = Field(default_factory=list)
    qa_report: QAReport | None = None
    rag_status: str = "not_needed"
    historical_bug_matches: list[HistoricalBugMatch] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    approval_history: list[dict[str, Any]] = Field(default_factory=list)
