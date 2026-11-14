import asyncio
import hashlib
import json
import logging
import statistics
import time
from collections.abc import Callable
from typing import Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.orm import Session

from app.ai.llm_provider import AIProviderError, StructuredOutputProvider
from app.ai.ollama_provider import create_llm_provider
from app.agents.bug_analysis_agent import BugAnalysisAgent
from app.agents.planning_agent import PlanningAgent
from app.agents.reporting_agent import ReportingAgent
from app.agents.requirement_agent import RequirementAnalysisAgent
from app.agents.test_generation_agent import TestGenerationAgent
from app.agents.website_understanding_agent import WebsiteUnderstandingAgent
from app.config import Settings, get_settings
from app.evaluation.datasets import get_dataset_samples
from app.evaluation.metrics.classification import (
    binary_classification_metrics,
    classification_metrics,
)
from app.evaluation.metrics.performance import performance_metrics
from app.evaluation.metrics.quality import evidence_support_metrics, term_recall
from app.evaluation.metrics.retrieval import retrieval_metrics
from app.evaluation.metrics.test_cases import calculate_test_generation_metrics
from app.evaluation.schemas import (
    EvaluationAgent,
    EvaluationExperimentResponse,
    EvaluationRunRequest,
    EvaluationSampleResult,
)
from app.graph.qa_graph import build_qa_graph
from app.models.evaluation import EvaluationExperiment
from app.rag.embeddings import get_embedding_service
from app.rag.schemas import KnowledgeSourceType
from app.rag.service import KnowledgeService
from app.rag.vector_store import ChromaVectorStore
from app.services.browser_inspection import BrowserInspectionService
from app.schemas.qa import (
    BugFinding,
    ExecutionResult,
    GeneratedTestCase,
    ReportFact,
    RequirementAnalysis,
    TestingPlan,
    WebsiteUnderstanding,
)

logger = logging.getLogger(__name__)


class EvaluationRunner:
    def __init__(
        self,
        *,
        provider_factory: Callable[[Settings], StructuredOutputProvider] = create_llm_provider,
        mock_provider: StructuredOutputProvider | None = None,
    ) -> None:
        self.provider_factory = provider_factory
        self.mock_provider = mock_provider

    def run(
        self,
        session: Session,
        request: EvaluationRunRequest,
    ) -> EvaluationExperimentResponse:
        dataset, samples = get_dataset_samples(
            request.dataset_id,
            request.agent,
            request.sample_ids,
        )
        settings = get_settings()
        if request.provider_mode == "mock":
            if self.mock_provider is None:
                raise ValueError(
                    "Mock mode is reserved for explicitly injected test providers."
                )
            provider = self.mock_provider
            provider_name = "mock"
            model_identifier = request.model_identifier or "injected-test-provider"
        elif request.agent is EvaluationAgent.RAG_RETRIEVAL:
            provider = None
            provider_name = "local-embedding"
            model_identifier = settings.rag_embedding_model
        else:
            if request.model_identifier:
                settings = settings.model_copy(
                    update={"ollama_model": request.model_identifier}
                )
            provider = self.provider_factory(settings)
            provider_name = settings.llm_provider
            model_identifier = settings.ollama_model

        started = time.perf_counter()
        sample_results: list[EvaluationSampleResult] = []
        bug_actual: list[bool] = []
        bug_predicted: list[bool] = []
        severity_actual: list[str] = []
        severity_predicted: list[str] = []
        durations: list[float] = []

        for run_number in range(1, request.repeat_count + 1):
            for sample in samples:
                sample_started = time.perf_counter()
                try:
                    sample_metrics = self._evaluate_sample(
                        sample.agent,
                        sample.inputs,
                        sample.ground_truth,
                        provider=provider,
                        rag_enabled=request.rag_enabled,
                        dataset_id=dataset.dataset_id,
                        sample_id=sample.sample_id,
                        run_number=run_number,
                        settings=settings,
                    )
                    duration_ms = (time.perf_counter() - sample_started) * 1000
                    if sample.agent is EvaluationAgent.BUG_ANALYSIS:
                        expected_bug = bool(sample.ground_truth["is_bug"])
                        predicted_bug = bool(sample_metrics["predicted_is_bug"])
                        bug_actual.append(expected_bug)
                        bug_predicted.append(predicted_bug)
                        severity_actual.append(
                            str(sample.ground_truth.get("severity", "INFO"))
                        )
                        severity_predicted.append(
                            str(sample_metrics.get("predicted_severity", "INFO"))
                        )
                    sample_results.append(
                        EvaluationSampleResult(
                            sample_id=sample.sample_id,
                            run_number=run_number,
                            status="completed",
                            duration_ms=duration_ms,
                            metrics=sample_metrics,
                        )
                    )
                except Exception as exc:
                    duration_ms = (time.perf_counter() - sample_started) * 1000
                    logger.warning(
                        "Evaluation sample failed agent=%s sample_id=%s error=%s",
                        sample.agent.value,
                        sample.sample_id,
                        type(exc).__name__,
                    )
                    sample_results.append(
                        EvaluationSampleResult(
                            sample_id=sample.sample_id,
                            run_number=run_number,
                            status="failed",
                            duration_ms=duration_ms,
                            error_category=type(exc).__name__,
                        )
                    )
                durations.append(duration_ms)

        completed = sum(item.status == "completed" for item in sample_results)
        failed = len(sample_results) - completed
        status = "completed" if failed == 0 else "failed" if completed == 0 else "partial"
        metrics = self._aggregate_metrics(sample_results)
        if request.agent is EvaluationAgent.BUG_ANALYSIS and bug_actual:
            metrics["bug_detection"] = binary_classification_metrics(
                bug_actual,
                bug_predicted,
            )
            metrics["severity_classification"] = classification_metrics(
                severity_actual,
                severity_predicted,
                labels=["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"],
            )
        total_duration = (time.perf_counter() - started) * 1000
        metrics["performance"] = performance_metrics(
            durations,
            failed_count=failed,
            total_count=len(sample_results),
        )

        limitations = [
            "Benchmark samples are synthetic and are not production accuracy evidence."
            if dataset.synthetic
            else "Dataset is not labeled as synthetic; inspect its provenance before interpreting results.",
            "LLM outputs are nondeterministic; repeat_count records repeated observations, not independent samples.",
            "Token usage is unavailable because the configured provider does not expose usage in this integration.",
            "Prompt version is an experiment label; this code version does not load historical prompt templates.",
        ]
        if request.provider_mode == "mock":
            limitations.append(
                "Mock-provider results validate evaluation plumbing only and are not model-quality measurements."
            )
        if request.agent is EvaluationAgent.WORKFLOW:
            limitations.append(
                "Workflow evaluation uses supplied synthetic inspection evidence and explicit benchmark approval confirmation; it never launches a browser."
            )
        configuration = {
            "agent": request.agent.value,
            "dataset_id": dataset.dataset_id,
            "dataset_version": dataset.version,
            "sample_ids": [sample.sample_id for sample in samples],
            "repeat_count": request.repeat_count,
            "provider_mode": request.provider_mode,
            "provider_name": provider_name,
            "model_identifier": model_identifier,
            "prompt_version": request.prompt_version,
            "rag_enabled": request.rag_enabled,
            "approval_confirmed": request.approval_confirmed,
        }
        record = EvaluationExperiment(
            experiment_name=f"{dataset.name} - {request.agent.value}",
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.version,
            agent_name=request.agent.value,
            provider_mode=request.provider_mode,
            provider_name=provider_name,
            model_identifier=model_identifier,
            prompt_version=request.prompt_version,
            rag_enabled=request.rag_enabled,
            status=status,
            configuration=configuration,
            metrics=metrics,
            sample_results=[
                item.model_dump(mode="json") for item in sample_results
            ],
            total_samples=len(sample_results),
            completed_samples=completed,
            failed_samples=failed,
            skipped_samples=0,
            run_count=request.repeat_count,
            duration_ms=total_duration,
            limitations=limitations,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return self.to_response(record)

    def _evaluate_sample(
        self,
        agent_name: EvaluationAgent,
        inputs: dict[str, Any],
        truth: dict[str, Any],
        *,
        provider: StructuredOutputProvider | None,
        rag_enabled: bool,
        dataset_id: str,
        sample_id: str,
        run_number: int,
        settings: Settings,
    ) -> dict[str, Any]:
        if agent_name is EvaluationAgent.RAG_RETRIEVAL:
            retrieved, metrics = self._evaluate_rag(
                inputs,
                truth,
                settings,
                dataset_id=dataset_id,
                sample_id=sample_id,
                run_number=run_number,
            )
            metrics["retrieved_documents"] = retrieved
            return metrics
        if provider is None:
            raise AIProviderError("No LLM provider was configured for this agent.")
        if agent_name is EvaluationAgent.WORKFLOW:
            output = asyncio.run(
                asyncio.wait_for(
                    self._run_workflow(inputs, provider),
                    timeout=settings.llm_timeout_seconds * 6,
                )
            )
            report = output.get("qa_report") or {}
            report_text = str(report.get("summary", "")) + " " + " ".join(
                report.get("recommendations", [])
            )
            finding_count = len(report.get("findings", []))
            maximum_findings = truth.get("required_findings_count_max")
            return {
                "workflow_completed": output.get("workflow_status") == "COMPLETED",
                "workflow_stage_count": 8,
                "required_report_term_recall": term_recall(
                    report_text,
                    truth.get("required_report_terms", []),
                ),
                "finding_count": finding_count,
                "unexpected_finding_count": (
                    max(0, finding_count - int(maximum_findings))
                    if maximum_findings is not None
                    else 0
                ),
                "finding_count_within_expected": (
                    finding_count <= int(maximum_findings)
                    if maximum_findings is not None
                    else True
                ),
                "rag_status": output.get("rag_status", "not_needed"),
            }

        agent = self._agent(agent_name, provider)
        if agent_name is EvaluationAgent.REQUIREMENT_ANALYSIS:
            call = agent.run(str(inputs["requirements"]))
        elif agent_name is EvaluationAgent.PLANNING:
            analysis = RequirementAnalysis.model_validate(inputs["analysis"])
            call = agent.run(analysis)
        elif agent_name is EvaluationAgent.WEBSITE_UNDERSTANDING:
            analysis = RequirementAnalysis.model_validate(inputs["analysis"])
            call = agent.run(analysis, inputs["evidence_index"])
        elif agent_name is EvaluationAgent.TEST_GENERATION:
            call = agent.run(
                RequirementAnalysis.model_validate(inputs["analysis"]),
                TestingPlan.model_validate(inputs["plan"]),
                WebsiteUnderstanding.model_validate(inputs["understanding"]),
                inputs["evidence_index"],
            )
        elif agent_name is EvaluationAgent.BUG_ANALYSIS:
            historical_context = (
                str(inputs.get("benchmark_historical_context", ""))
                if rag_enabled
                else ""
            )
            call = agent.run(
                inputs["execution_results"],
                inputs["evidence_index"],
                historical_context=historical_context,
                historical_references=set(inputs.get("historical_references", []))
                if rag_enabled
                else set(),
            )
        elif agent_name is EvaluationAgent.REPORTING:
            tests = [
                GeneratedTestCase.model_validate(item)
                for item in inputs["tests"]
            ]
            results = [
                ExecutionResult.model_validate(item)
                for item in inputs["results"]
            ]
            findings = [
                BugFinding.model_validate(item)
                for item in inputs["findings"]
            ]
            observed_facts = [
                ReportFact.model_validate(item)
                for item in inputs.get("observed_facts", [])
            ]
            call = agent.run(
                UUID(str(inputs["execution_id"])),
                tests,
                results,
                findings,
                observed_facts,
            )
        else:
            raise ValueError("Selected evaluator is not supported.")
        output = asyncio.run(
            asyncio.wait_for(call, timeout=settings.llm_timeout_seconds)
        )
        return self._score(agent_name, output, truth, inputs)

    @staticmethod
    def _agent(
        name: EvaluationAgent,
        provider: StructuredOutputProvider,
    ) -> Any:
        agents = {
            EvaluationAgent.REQUIREMENT_ANALYSIS: RequirementAnalysisAgent,
            EvaluationAgent.PLANNING: PlanningAgent,
            EvaluationAgent.WEBSITE_UNDERSTANDING: WebsiteUnderstandingAgent,
            EvaluationAgent.TEST_GENERATION: TestGenerationAgent,
            EvaluationAgent.BUG_ANALYSIS: BugAnalysisAgent,
            EvaluationAgent.REPORTING: ReportingAgent,
        }
        if name not in agents:
            raise ValueError("Selected evaluator is not an individual LLM agent.")
        return agents[name](provider)

    async def _run_workflow(
        self,
        inputs: dict[str, Any],
        provider: StructuredOutputProvider,
    ) -> dict[str, Any]:
        class ControlledInspectionService:
            settings = get_settings()
            last_artifacts: list[dict[str, Any]] = []

            async def inspect(
                self,
                execution_id: UUID,
                target_url: str,
            ) -> dict[str, Any]:
                del execution_id, target_url
                return dict(inputs["inspection"])

        project_id = uuid5(
            NAMESPACE_URL,
            f"evaluation-workflow:{inputs['execution_id']}",
        )
        service = KnowledgeService(
            embeddings=get_embedding_service(),
            vector_store=ChromaVectorStore(
                get_settings().chroma_persist_path,
                f"eval_{hashlib.sha256(str(project_id).encode()).hexdigest()[:20]}",
                ephemeral=True,
            ),
        )
        graph = build_qa_graph(
            provider,
            cast(
                BrowserInspectionService,
                ControlledInspectionService(),
            ),
            knowledge_service=service,
        )
        initial_state = {
            "project_id": str(project_id),
            "execution_id": str(inputs["execution_id"]),
            "target_url": str(inputs["inspection"]["requested_url"]),
            "user_requirements": str(inputs["requirements"]),
            "approval_status": "APPROVED",
            "approval_phase": "INSPECTION",
            "workflow_status": "RUNNING",
            "errors": [],
            "warnings": [],
        }
        waiting = await graph.ainvoke(initial_state)
        if waiting.get("workflow_status") != "WAITING_APPROVAL":
            raise RuntimeError("QA workflow did not stop at its test-plan approval gate.")
        resumed_state = {
            **waiting,
            "resume_node": "check_approval",
            "approval_status": "APPROVED",
            "approval_phase": "TEST_PLAN",
        }
        return await graph.ainvoke(resumed_state)

    @staticmethod
    def _score(
        agent: EvaluationAgent,
        output: Any,
        truth: dict[str, Any],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        rendered = (
            json.dumps(output.model_dump(mode="json"), ensure_ascii=True)
            if hasattr(output, "model_dump")
            else str(output)
        )
        if agent is EvaluationAgent.REQUIREMENT_ANALYSIS:
            return {
                "required_term_recall": term_recall(
                    rendered,
                    truth.get("required_terms", []),
                ),
                "generated_requirement_count": len(output.functional_requirements),
            }
        if agent is EvaluationAgent.PLANNING:
            expected = set(truth.get("expected_requirement_ids", []))
            actual = {task.requirement_ref for task in output.tasks}
            return {
                "requirement_coverage": (
                    len(expected & actual) / len(expected) if expected else 0.0
                ),
                "planned_task_count": len(output.tasks),
                "objective_term_recall": term_recall(
                    rendered,
                    truth.get("expected_objective_terms", []),
                ),
            }
        if agent is EvaluationAgent.WEBSITE_UNDERSTANDING:
            expected = set(truth.get("supported_requirement_ids", []))
            actual = {
                item.requirement_id
                for item in output.requirement_evidence
                if item.support == "SUPPORTED"
            }
            refs = {
                reference
                for item in output.requirement_evidence
                for reference in item.evidence_references
            } | set(output.observed_element_references)
            return {
                "supported_requirement_precision": (
                    len(actual & expected) / len(actual) if actual else 0.0
                ),
                "supported_requirement_recall": (
                    len(actual & expected) / len(expected) if expected else 0.0
                ),
                "evidence_reference_precision": (
                    len(refs & set(inputs["evidence_index"])) / len(refs)
                    if refs
                    else 1.0
                ),
                "expected_evidence_coverage": (
                    len(refs & set(truth.get("expected_evidence_references", [])))
                    / len(set(truth.get("expected_evidence_references", [])))
                    if truth.get("expected_evidence_references")
                    else 1.0
                ),
            }
        if agent is EvaluationAgent.TEST_GENERATION:
            expected_requirements = set(truth.get("expected_requirement_ids", []))
            generated_requirements = {case.requirement_id for case in output.test_cases}
            allowed_requirements = {
                item["requirement_id"]
                for item in inputs["analysis"]["functional_requirements"]
            }
            available_evidence = set(inputs["evidence_index"])
            scenario_terms = truth.get("expected_scenario_terms", [])
            matched_scenarios = {
                term for term in scenario_terms if term.casefold() in rendered.casefold()
            }
            supported_cases = [
                case
                for case in output.test_cases
                if case.requirement_id in allowed_requirements
                and set(case.evidence_requirements) <= available_evidence
            ]
            titles = [
                " ".join((case.title, case.description)).casefold().strip()
                for case in output.test_cases
            ]
            duplicates = len(titles) - len(set(titles))
            return calculate_test_generation_metrics(
                expected_requirements=expected_requirements,
                covered_requirements=generated_requirements,
                expected_scenarios=set(scenario_terms),
                generated_scenarios=matched_scenarios,
                generated_count=len(output.test_cases),
                relevant_generated_count=len(supported_cases),
                duplicate_count=duplicates,
                unsupported_count=len(output.test_cases) - len(supported_cases),
            )
        if agent is EvaluationAgent.BUG_ANALYSIS:
            findings = output.findings
            predicted_bug = bool(findings)
            top = findings[0] if findings else None
            cited = {
                reference
                for finding in findings
                for reference in finding.supporting_evidence
            }
            quality = evidence_support_metrics(
                cited_evidence=cited,
                available_evidence=set(inputs["evidence_index"]),
                expected_evidence=set(truth.get("expected_evidence", [])),
            )
            quality["root_cause_term_recall"] = term_recall(
                " ".join(
                    (
                        top.title,
                        top.description,
                        top.probable_root_cause,
                        top.recommended_action,
                    )
                )
                if top
                else "",
                truth.get("root_cause_terms", []),
            )
            quality["recommendation_term_recall"] = term_recall(
                top.recommended_action if top else "",
                truth.get(
                    "recommendation_terms",
                    truth.get("root_cause_terms", []),
                ),
            )
            quality["hallucination_indicator_count"] = quality[
                "unsupported_claim_count"
            ]
            quality["predicted_is_bug"] = predicted_bug
            quality["predicted_severity"] = top.severity.value if top else "INFO"
            return quality
        if agent is EvaluationAgent.REPORTING:
            full_text = output.summary + " " + " ".join(output.recommendations)
            return {
                "summary_term_recall": term_recall(
                    output.summary,
                    truth.get("required_summary_terms", []),
                ),
                "recommendation_term_recall": term_recall(
                    " ".join(output.recommendations),
                    truth.get("required_recommendation_terms", []),
                ),
                "required_report_term_recall": term_recall(
                    full_text,
                    truth.get("required_summary_terms", [])
                    + truth.get("required_recommendation_terms", []),
                ),
            }
        raise ValueError("No deterministic scorer is defined for this agent.")

    @staticmethod
    def _evaluate_rag(
        inputs: dict[str, Any],
        truth: dict[str, Any],
        settings: Settings,
        *,
        dataset_id: str,
        sample_id: str,
        run_number: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        embedding_service = get_embedding_service(
            settings.rag_embedding_model,
            settings.rag_embedding_device,
        )
        if not settings.rag_enabled:
            raise RuntimeError("RAG evaluation is disabled by configuration.")
        embedding_started = time.perf_counter()
        query_vector = embedding_service.embed_query(str(inputs["query"]))
        embedding_duration_ms = (time.perf_counter() - embedding_started) * 1000
        project_id = uuid5(
            NAMESPACE_URL,
            f"evaluation:{dataset_id}:{sample_id}:{run_number}:{inputs['project_scope']}",
        )
        store = ChromaVectorStore(
            settings.chroma_persist_path,
            f"eval_{hashlib.sha256(str(project_id).encode()).hexdigest()[:20]}",
            ephemeral=True,
        )
        service = KnowledgeService(
            embeddings=embedding_service,
            vector_store=store,
        )
        external_id_by_reference: dict[str, str] = {}
        ingestion_started = time.perf_counter()
        for document in inputs["documents"]:
            source_type = KnowledgeSourceType(document["source_type"])
            service.ingest_text(
                content=document["content"],
                title=document["title"],
                project_id=project_id,
                source_type=source_type,
                source_reference=document["source_reference"],
                severity=document.get("severity"),
            )
            external_id_by_reference[document["source_reference"]] = document[
                "document_id"
            ]
        ingestion_ms = (time.perf_counter() - ingestion_started) * 1000
        retrieval_started = time.perf_counter()
        retrieved = service.search(
            str(inputs["query"]),
            project_id=project_id,
            top_k=int(inputs["top_k"]),
        )
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
        ranked_ids = [
            external_id_by_reference[item.source_reference]
            for item in retrieved
            if item.source_reference in external_id_by_reference
        ]
        relevance = retrieval_metrics(
            set(truth["relevant_document_ids"]),
            ranked_ids,
            k=int(truth["k"]),
            relevance_grades=truth.get("relevance_grades"),
        )
        context = service.build_context(retrieved)
        relevance["embedding_dimension"] = len(query_vector)
        relevance["embedding_generation_duration_ms"] = embedding_duration_ms
        relevance["indexing_duration_ms"] = ingestion_ms
        relevance["retrieval_duration_ms"] = retrieval_ms
        relevance["context_chars"] = len(context)
        relevance["context_within_limit"] = (
            len(context) <= settings.rag_max_context_chars
        )
        relevance["context_duplicate_count"] = (
            len(retrieved) - len({item.document_id for item in retrieved})
        )
        relevance["source_reference_preserved"] = all(
            item.source_reference for item in retrieved
        )
        relevance["project_scope_isolated"] = all(
            item.metadata.get("project_id") == str(project_id)
            for item in retrieved
        )
        return [
            {
                "document_id": external_id_by_reference.get(
                    item.source_reference,
                    item.document_id,
                ),
                "source_reference": item.source_reference,
                "similarity_score": item.similarity_score,
            }
            for item in retrieved
        ], relevance

    @staticmethod
    def _aggregate_metrics(
        results: list[EvaluationSampleResult],
    ) -> dict[str, Any]:
        completed = [item for item in results if item.status == "completed"]
        keys = {
            key
            for item in completed
            for key, value in item.metrics.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        aggregate: dict[str, Any] = {}
        for key in sorted(keys):
            values = [
                float(item.metrics[key])
                for item in completed
                if isinstance(item.metrics.get(key), (int, float))
                and not isinstance(item.metrics.get(key), bool)
            ]
            if values:
                aggregate[key] = statistics.fmean(values)
                if len(values) > 1:
                    aggregate[f"{key}_stddev"] = statistics.stdev(values)
        boolean_keys = {
            key
            for item in completed
            for key, value in item.metrics.items()
            if isinstance(value, bool)
        }
        for key in boolean_keys:
            values = [
                item.metrics[key]
                for item in completed
                if isinstance(item.metrics.get(key), bool)
            ]
            aggregate[key] = all(values)
        aggregate["total_sample_count"] = len(results)
        aggregate["completed_sample_count"] = len(completed)
        aggregate["failed_sample_count"] = len(results) - len(completed)
        aggregate["skipped_sample_count"] = 0
        return aggregate

    @staticmethod
    def to_response(record: EvaluationExperiment) -> EvaluationExperimentResponse:
        return EvaluationExperimentResponse(
            id=record.id,
            experiment_name=record.experiment_name,
            dataset_id=record.dataset_id,
            dataset_version=record.dataset_version,
            agent=EvaluationAgent(record.agent_name),
            provider_mode=record.provider_mode,
            provider_name=record.provider_name,
            model_identifier=record.model_identifier,
            prompt_version=record.prompt_version,
            rag_enabled=record.rag_enabled,
            status=record.status,
            configuration=record.configuration,
            metrics=record.metrics,
            sample_results=record.sample_results,
            total_samples=record.total_samples,
            completed_samples=record.completed_samples,
            failed_samples=record.failed_samples,
            skipped_samples=record.skipped_samples,
            run_count=record.run_count,
            duration_ms=record.duration_ms,
            created_at=record.created_at,
            limitations=record.limitations,
        )
