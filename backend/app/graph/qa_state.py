from typing import Any, TypedDict


class QAState(TypedDict, total=False):
    project_id: str
    execution_id: str
    target_url: str
    user_requirements: str
    requirement_analysis: dict[str, Any] | None
    testing_plan: dict[str, Any] | None
    website_inspection: dict[str, Any] | None
    website_understanding: dict[str, Any] | None
    generated_test_cases: list[dict[str, Any]]
    execution_results: list[dict[str, Any]]
    bug_findings: list[dict[str, Any]]
    qa_report: dict[str, Any] | None
    rag_query: str
    retrieved_documents: list[dict[str, Any]]
    retrieval_metadata: dict[str, Any]
    historical_bug_matches: list[dict[str, Any]]
    rag_context: str
    rag_status: str
    approval_status: str | None
    approval_phase: str
    approval_history: list[dict[str, Any]]
    current_agent: str
    workflow_status: str
    errors: list[dict[str, str]]
    warnings: list[str]
    evidence_index: dict[str, Any]
    inspection_artifacts: list[dict[str, Any]]
    resume_node: str | None
