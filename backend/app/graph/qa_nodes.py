import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from app.agents import (
    BugAnalysisAgent,
    PlanningAgent,
    ReportingAgent,
    RequirementAnalysisAgent,
    TestGenerationAgent,
    WebsiteUnderstandingAgent,
)
from app.ai.llm_provider import AIProviderError, StructuredOutputProvider
from app.schemas.qa import (
    ApprovalPhase,
    BugFinding,
    ElementKind,
    ExecutionResult,
    GeneratedTestCase,
    HistoricalBugMatch,
    QAReport,
    ReportFact,
    RequirementAnalysis,
    TestOutcome,
    TestType,
    TestingPlan,
    ValidationKind,
    WebsiteUnderstanding,
)
from app.services.browser_inspection import (
    BrowserInspectionFailure,
    BrowserInspectionService,
    sanitize_url,
)
from app.graph.qa_state import QAState
from app.rag.chunking import sanitize_knowledge_text
from app.rag.service import KnowledgeService, create_knowledge_service

logger = logging.getLogger(__name__)

Operation = Callable[[], Awaitable[dict[str, Any]]]
_ELEMENT_KEYS = {
    ElementKind.BUTTON: "buttons",
    ElementKind.LINK: "links",
    ElementKind.INPUT: "inputs",
    ElementKind.SELECT: "selects",
    ElementKind.TEXTAREA: "textareas",
    ElementKind.FORM: "forms",
}


def _compact(value: Any, *, limit: int = 200) -> Any:
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, list):
        return [_compact(item, limit=limit) for item in value[:5]]
    if isinstance(value, dict):
        return {
            str(key)[:80]: _compact(item, limit=limit)
            for key, item in list(value.items())[:6]
        }
    return value


def build_evidence_index(inspection: dict[str, Any]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    for key in (
        "requested_url",
        "final_url",
        "title",
        "navigation_status",
        "page_load_status",
    ):
        if key in inspection and inspection[key] is not None:
            evidence[f"page.{key}"] = inspection[key]
    interactive = inspection.get("interactive_elements", {})
    if isinstance(interactive, dict):
        if "total_count" in interactive:
            evidence["elements.total_count"] = interactive["total_count"]
        evidence["elements.truncated"] = bool(interactive.get("truncated", False))
        for kind in ("buttons", "links", "inputs", "selects", "textareas", "forms"):
            items = interactive.get(kind, [])
            if isinstance(items, list):
                evidence[f"elements.{kind}.count"] = len(items)
                for index, item in enumerate(items[:3]):
                    evidence[f"elements.{kind}[{index}]"] = _compact(item)
    events = inspection.get("events", {})
    if isinstance(events, dict):
        for kind in ("console", "page_errors", "network"):
            items = events.get(kind, [])
            if isinstance(items, list):
                for index, item in enumerate(items[:3]):
                    evidence[f"events.{kind}[{index}]"] = _compact(item)
    return evidence


def _failure(
    state: QAState,
    *,
    agent: str,
    code: str,
    message: str,
) -> dict[str, Any]:
    logger.error("QA workflow agent %s failed: %s", agent, code)
    errors = list(state.get("errors", []))
    errors.append({"agent": agent, "code": code, "message": message})
    return {
        "current_agent": agent,
        "workflow_status": "FAILED",
        "errors": errors,
    }


async def _guarded(
    state: QAState,
    agent: str,
    operation: Operation,
) -> dict[str, Any]:
    try:
        return await operation()
    except AIProviderError as exc:
        return _failure(
            state,
            agent=agent,
            code="ai_provider_error",
            message=str(exc),
        )
    except BrowserInspectionFailure as exc:
        inspection = dict(exc.result)
        inspection["requested_url"] = sanitize_url(state["target_url"])
        return {
            **_failure(
                state,
                agent=agent,
                code=exc.code,
                message=str(exc),
            ),
            "website_inspection": inspection,
            "inspection_artifacts": exc.artifacts,
            "evidence_index": build_evidence_index(inspection),
        }
    except Exception as exc:
        logger.exception(
            "Unexpected QA workflow failure in %s (%s)",
            agent,
            type(exc).__name__,
        )
        return _failure(
            state,
            agent=agent,
            code="agent_execution_failed",
            message=f"{agent} failed unexpectedly. Check application logs.",
        )


def _parse_analysis(state: QAState) -> RequirementAnalysis:
    return RequirementAnalysis.model_validate(state["requirement_analysis"])


def _parse_plan(state: QAState) -> TestingPlan:
    return TestingPlan.model_validate(state["testing_plan"])


def _parse_understanding(state: QAState) -> WebsiteUnderstanding:
    return WebsiteUnderstanding.model_validate(state["website_understanding"])


def create_qa_nodes(
    provider: StructuredOutputProvider,
    inspection_service: BrowserInspectionService,
    knowledge_service: KnowledgeService | None = None,
) -> dict[str, Callable[[QAState], Awaitable[dict[str, Any]]]]:
    requirement_agent = RequirementAnalysisAgent(provider)
    planning_agent = PlanningAgent(provider)
    website_agent = WebsiteUnderstandingAgent(provider)
    generation_agent = TestGenerationAgent(provider)
    bug_agent = BugAnalysisAgent(provider)
    reporting_agent = ReportingAgent(provider)
    rag_service = knowledge_service or create_knowledge_service()

    async def analyze_requirements(state: QAState) -> dict[str, Any]:
        async def run() -> dict[str, Any]:
            result = await requirement_agent.run(state["user_requirements"])
            return {
                "current_agent": "requirement_analysis",
                "requirement_analysis": result.model_dump(mode="json"),
            }

        return await _guarded(state, "requirement_analysis", run)

    async def create_test_plan(state: QAState) -> dict[str, Any]:
        async def run() -> dict[str, Any]:
            result = await planning_agent.run(_parse_analysis(state))
            return {
                "current_agent": "planning",
                "testing_plan": result.model_dump(mode="json"),
            }

        return await _guarded(state, "planning", run)

    async def check_approval(state: QAState) -> dict[str, Any]:
        if state.get("approval_status") == "REJECTED":
            return {
                "current_agent": "check_approval",
                "workflow_status": "CANCELLED",
                "errors": [
                    {
                        "agent": "check_approval",
                        "code": "approval_rejected",
                        "message": (
                            f"The {state.get('approval_phase', 'workflow')} "
                            "approval was rejected."
                        ),
                    }
                ],
            }
        if state.get("approval_status") != "APPROVED":
            return {
                "current_agent": "check_approval",
                "workflow_status": "WAITING_APPROVAL",
            }
        return {
            "current_agent": "check_approval",
            "workflow_status": "RUNNING",
            "resume_node": None,
        }

    async def inspect_website(state: QAState) -> dict[str, Any]:
        async def run() -> dict[str, Any]:
            result = await asyncio.wait_for(
                inspection_service.inspect(
                    UUID(state["execution_id"]),
                    state["target_url"],
                ),
                timeout=(
                    inspection_service.settings.browser_execution_timeout_ms / 1000
                ),
            )
            result["requested_url"] = sanitize_url(state["target_url"])
            return {
                "current_agent": "website_inspection",
                "website_inspection": result,
                "inspection_artifacts": inspection_service.last_artifacts,
                "evidence_index": build_evidence_index(result),
            }

        return await _guarded(state, "website_inspection", run)

    async def understand_website(state: QAState) -> dict[str, Any]:
        async def run() -> dict[str, Any]:
            inspection = state.get("website_inspection")
            if not inspection:
                raise ValueError("Website inspection evidence is unavailable.")
            evidence = build_evidence_index(inspection)
            result = await website_agent.run(
                _parse_analysis(state),
                evidence,
            )
            return {
                "current_agent": "website_understanding",
                "website_understanding": result.model_dump(mode="json"),
                "evidence_index": evidence,
            }

        return await _guarded(state, "website_understanding", run)

    async def generate_test_cases(state: QAState) -> dict[str, Any]:
        async def run() -> dict[str, Any]:
            inspection = state.get("website_inspection")
            if not inspection:
                raise ValueError("Website inspection evidence is unavailable.")
            result = await generation_agent.run(
                _parse_analysis(state),
                _parse_plan(state),
                _parse_understanding(state),
                build_evidence_index(inspection),
            )
            return {
                "current_agent": "test_generation",
                "generated_test_cases": [
                    case.model_dump(mode="json") for case in result.test_cases
                ],
                "approval_status": "PENDING",
                "approval_phase": ApprovalPhase.TEST_PLAN.value,
            }

        return await _guarded(state, "test_generation", run)

    async def coordinate_execution(state: QAState) -> dict[str, Any]:
        inspection = state.get("website_inspection")
        if not inspection:
            return _failure(
                state,
                agent="execution_coordination",
                code="inspection_unavailable",
                message="The approved browser inspection result is unavailable.",
            )
        evidence = build_evidence_index(inspection)
        elements = inspection.get("interactive_elements", {})
        results: list[ExecutionResult] = []
        prior: dict[str, TestOutcome] = {}
        for raw_case in state.get("generated_test_cases", []):
            case = GeneratedTestCase.model_validate(raw_case)
            blocked_by = [
                dependency
                for dependency in case.depends_on
                if prior.get(dependency) is not TestOutcome.PASSED
            ]
            if blocked_by:
                result = ExecutionResult(
                    test_case_id=case.test_case_id,
                    status=TestOutcome.SKIPPED,
                    summary="Skipped because a prerequisite test did not pass.",
                    unsupported_reason=", ".join(blocked_by),
                )
            elif "error" in inspection or inspection.get("navigation_status") is None:
                result = ExecutionResult(
                    test_case_id=case.test_case_id,
                    status=TestOutcome.BLOCKED,
                    summary="Inspection evidence was insufficient to evaluate this test.",
                )
            elif (
                case.test_type
                not in {TestType.PAGE_LOAD, TestType.ELEMENT_PRESENCE}
                or case.validation_criteria.kind is ValidationKind.UNSUPPORTED
            ):
                result = ExecutionResult(
                    test_case_id=case.test_case_id,
                    status=TestOutcome.NOT_SUPPORTED,
                    summary=(
                        "The existing browser engine supports read-only inspection "
                        "only; this test requires an unsupported action or validator."
                    ),
                    unsupported_reason=case.test_type.value,
                )
            elif (
                case.test_type is TestType.PAGE_LOAD
                and case.validation_criteria.kind is ValidationKind.PAGE_LOAD
            ):
                status_code = inspection.get("navigation_status")
                passed = isinstance(status_code, int) and 200 <= status_code < 400
                result = ExecutionResult(
                    test_case_id=case.test_case_id,
                    status=TestOutcome.PASSED if passed else TestOutcome.FAILED,
                    summary=(
                        "Page navigation returned a successful HTTP status."
                        if passed
                        else "Page navigation returned an unsuccessful HTTP status."
                    ),
                    actual_result=f"HTTP {status_code}",
                    evidence_references=["page.navigation_status"],
                )
            elif (
                case.test_type is TestType.ELEMENT_PRESENCE
                and case.validation_criteria.kind is ValidationKind.ELEMENT_COUNT
                and isinstance(elements, dict)
            ):
                kind = case.validation_criteria.element_kind
                assert kind is not None
                list_key = _ELEMENT_KEYS[kind]
                count = len(elements.get(list_key, []))
                passed = count >= (case.validation_criteria.minimum_count or 1)
                count_evidence = f"elements.{list_key}.count"
                if passed:
                    result = ExecutionResult(
                        test_case_id=case.test_case_id,
                        status=TestOutcome.PASSED,
                        summary=(
                            f"Observed {count} {kind.value.lower()} element(s)."
                        ),
                        actual_result=f"Observed count: {count}",
                        evidence_references=(
                            [count_evidence] if count_evidence in evidence else []
                        ),
                    )
                else:
                    possibly_truncated = bool(elements.get("truncated"))
                    result = ExecutionResult(
                        test_case_id=case.test_case_id,
                        status=TestOutcome.BLOCKED,
                        summary=(
                            "The requested element count was not confirmed by "
                            "the bounded read-only inspection"
                            + (
                                "; the element inventory was truncated."
                                if possibly_truncated
                                else "."
                            )
                        ),
                        actual_result=f"Observed count: {count}",
                        evidence_references=(
                            [count_evidence] if count_evidence in evidence else []
                        ),
                    )
            else:
                result = ExecutionResult(
                    test_case_id=case.test_case_id,
                    status=TestOutcome.EXECUTED,
                    summary=(
                        "Read-only inspection completed, but the specified "
                        "validation criteria could not be evaluated."
                    ),
                )
            prior[case.test_case_id] = result.status
            results.append(result)
        return {
            "current_agent": "execution_coordination",
            "execution_results": [
                item.model_dump(mode="json") for item in results
            ],
        }

    async def retrieve_historical_knowledge(state: QAState) -> dict[str, Any]:
        if not rag_service.settings.rag_enabled:
            return {
                "current_agent": "historical_knowledge_retrieval",
                "rag_status": "disabled",
                "rag_query": "",
                "retrieved_documents": [],
                "retrieval_metadata": {"result_count": 0},
                "historical_bug_matches": [],
                "rag_context": "",
            }
        inspection = state.get("website_inspection") or {}
        results = state.get("execution_results", [])
        events = inspection.get("events", {})
        has_issue = any(
            item.get("status") == TestOutcome.FAILED.value
            for item in results
            if isinstance(item, dict)
        ) or bool(events.get("page_errors")) or bool(events.get("network")) or any(
            item.get("type") == "error"
            for item in events.get("console", [])
            if isinstance(item, dict)
        )
        if not has_issue:
            return {
                "current_agent": "historical_knowledge_retrieval",
                "rag_status": "not_needed",
                "rag_query": "",
                "retrieved_documents": [],
                "retrieval_metadata": {"result_count": 0},
                "historical_bug_matches": [],
                "rag_context": "",
            }
        query_payload = {
            "failed_tests": [
                item for item in results
                if isinstance(item, dict)
                and item.get("status") == TestOutcome.FAILED.value
            ],
            "page_errors": events.get("page_errors", []),
            "network_errors": events.get("network", []),
            "console_errors": [
                item for item in events.get("console", [])
                if isinstance(item, dict) and item.get("type") == "error"
            ],
            "affected_url": inspection.get("final_url")
            or inspection.get("requested_url"),
        }
        query = sanitize_knowledge_text(
            json.dumps(query_payload, ensure_ascii=True, default=str)
        )[:4000]
        try:
            project_id = UUID(state["project_id"])
            documents = await asyncio.to_thread(
                rag_service.search,
                query,
                project_id=project_id,
            )
            bug_matches = [
                HistoricalBugMatch(
                    document_id=item.document_id,
                    title=str(item.metadata.get("title", "Historical finding")),
                    source_reference=item.source_reference,
                    similarity_score=item.similarity_score,
                    severity=item.metadata.get("severity"),
                    execution_id=item.metadata.get("execution_id"),
                )
                for item in documents
                if item.source_type.value == "historical_bug"
            ]
            return {
                "current_agent": "historical_knowledge_retrieval",
                "rag_status": "success" if documents else "empty",
                "rag_query": query,
                "retrieved_documents": [
                    item.model_dump(mode="json") for item in documents
                ],
                "retrieval_metadata": {
                    "result_count": len(documents),
                    "project_scope": state["project_id"],
                    "similarity_score_is_probability": False,
                },
                "historical_bug_matches": [
                    item.model_dump(mode="json") for item in bug_matches
                ],
                "rag_context": rag_service.build_context(documents),
            }
        except Exception as exc:
            logger.warning(
                "Historical retrieval unavailable for project %s (%s)",
                state.get("project_id"),
                type(exc).__name__,
            )
            return {
                "current_agent": "historical_knowledge_retrieval",
                "rag_status": "unavailable",
                "rag_query": query,
                "retrieved_documents": [],
                "retrieval_metadata": {
                    "result_count": 0,
                    "error_category": type(exc).__name__,
                    "project_scope": state.get("project_id"),
                },
                "historical_bug_matches": [],
                "rag_context": "",
                "warnings": list(state.get("warnings", []))
                + [
                    "Historical knowledge retrieval was unavailable; "
                    "bug analysis continued without it."
                ],
            }

    async def analyze_bugs(state: QAState) -> dict[str, Any]:
        async def run() -> dict[str, Any]:
            inspection = state.get("website_inspection") or {}
            results = state.get("execution_results", [])
            events = inspection.get("events", {})
            console_errors = any(
                item.get("type") == "error"
                for item in events.get("console", [])
                if isinstance(item, dict)
            )
            has_browser_errors = (
                console_errors
                or bool(events.get("page_errors"))
                or bool(events.get("network"))
            )
            has_test_failures = any(
                item.get("status") == TestOutcome.FAILED.value
                for item in results
            )
            if not has_test_failures and not has_browser_errors:
                return {
                    "current_agent": "bug_analysis",
                    "bug_findings": [],
                }
            evidence = build_evidence_index(inspection)
            failed_results = [
                item
                for item in results
                if item.get("status") == TestOutcome.FAILED.value
            ]
            historical_matches = state.get("historical_bug_matches", [])
            allowed_historical_references = {
                item["source_reference"]
                for item in historical_matches
                if isinstance(item, dict) and item.get("source_reference")
            }
            findings = await bug_agent.run(
                failed_results,
                evidence,
                state.get("rag_context", ""),
                allowed_historical_references,
            )
            return {
                "current_agent": "bug_analysis",
                "bug_findings": [
                    finding.model_dump(mode="json")
                    for finding in findings.findings
                ],
            }

        return await _guarded(state, "bug_analysis", run)

    async def generate_report(state: QAState) -> dict[str, Any]:
        async def run() -> dict[str, Any]:
            cases = [
                GeneratedTestCase.model_validate(item)
                for item in state.get("generated_test_cases", [])
            ]
            results = [
                ExecutionResult.model_validate(item)
                for item in state.get("execution_results", [])
            ]
            findings = [
                BugFinding.model_validate(item)
                for item in state.get("bug_findings", [])
            ]
            facts = _observed_facts(state.get("website_inspection") or {})
            report: QAReport = await reporting_agent.run(
                UUID(state["execution_id"]),
                cases,
                results,
                findings,
                facts,
                rag_status=state.get("rag_status", "not_needed"),
                historical_bug_matches=[
                    item
                    for item in state.get("historical_bug_matches", [])
                ],
            )
            return {
                "current_agent": "reporting",
                "qa_report": report.model_dump(mode="json"),
                "workflow_status": "COMPLETED",
            }

        return await _guarded(state, "reporting", run)

    async def handle_workflow_error(state: QAState) -> dict[str, Any]:
        cancelled = state.get("workflow_status") == "CANCELLED"
        return {
            "current_agent": "workflow_error_handler",
            "workflow_status": "CANCELLED" if cancelled else "FAILED",
        }

    return {
        "analyze_requirements": analyze_requirements,
        "create_test_plan": create_test_plan,
        "check_approval": check_approval,
        "inspect_website": inspect_website,
        "understand_website": understand_website,
        "generate_test_cases": generate_test_cases,
        "coordinate_execution": coordinate_execution,
        "retrieve_historical_knowledge": retrieve_historical_knowledge,
        "analyze_bugs": analyze_bugs,
        "generate_report": generate_report,
        "handle_workflow_error": handle_workflow_error,
    }


def _observed_facts(inspection: dict[str, Any]) -> list[ReportFact]:
    facts: list[ReportFact] = []
    status = inspection.get("navigation_status")
    if isinstance(status, int):
        facts.append(
            ReportFact(
                fact=f"Observed browser navigation HTTP status {status}.",
                evidence_references=["page.navigation_status"],
            )
        )
    title = inspection.get("title")
    if isinstance(title, str) and title:
        facts.append(
            ReportFact(
                fact=f"Observed page title: {title[:500]}",
                evidence_references=["page.title"],
            )
        )
    interactive = inspection.get("interactive_elements")
    if isinstance(interactive, dict) and isinstance(
        interactive.get("total_count"), int
    ):
        facts.append(
            ReportFact(
                fact=(
                    "Observed "
                    f"{interactive['total_count']} interactive element(s)."
                ),
                evidence_references=["elements.total_count"],
            )
        )
    events = inspection.get("events", {})
    if isinstance(events, dict):
        for kind in ("console", "page_errors", "network"):
            for index, item in enumerate(events.get(kind, [])[:5]):
                facts.append(
                    ReportFact(
                        fact=f"Observed {kind} event: {str(item)[:700]}",
                        evidence_references=[f"events.{kind}[{index}]"],
                    )
                )
    return facts
