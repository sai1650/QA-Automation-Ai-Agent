import math
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from app.ai.prompt_templates import bug_analysis_prompt
from app.evaluation.datasets import get_dataset_samples, list_datasets, load_dataset
from app.evaluation.metrics.classification import (
    binary_classification_metrics,
    classification_metrics,
)
from app.evaluation.metrics.retrieval import retrieval_metrics
from app.evaluation.metrics.test_cases import calculate_test_generation_metrics
from app.evaluation.runner import EvaluationRunner
from app.evaluation.schemas import EvaluationAgent, EvaluationRunRequest
from app.evaluation.service import EvaluationService
from app.dependencies import get_evaluation_service
from app.main import app
from app.schemas.finding import Severity
from app.schemas.qa import (
    BugFindingSet,
    RequirementAnalysis,
    ReportNarrative,
    TestCaseSet as QATestCaseSet,
    TestingPlan as QATestingPlan,
    WebsiteUnderstanding,
)


class DatasetMockProvider:
    async def generate(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        if schema is RequirementAnalysis:
            data: dict[str, Any] = {
                "objectives": ["Check catalog keyword search."],
                "functional_requirements": [
                    {
                        "requirement_id": "REQ-01",
                        "description": "Visitors can search the product catalog by keyword.",
                        "expected_behavior": "Matching product names are shown.",
                    }
                ],
                "constraints": ["Do not submit forms or change account data."],
                "limitations": ["Read-only inspection only."],
                "ambiguities": [],
                "missing_information": [],
            }
        elif schema is QATestingPlan:
            data = {
                "tasks": [
                    {
                        "test_id": "TASK-01",
                        "objective": "Inspect the catalog search input.",
                        "requirement_ref": "REQ-01",
                        "priority": "P1",
                        "prerequisites": [],
                        "risk": "The input may be absent.",
                        "expected_outcome": "The page exposes a search input.",
                        "required_evidence": ["elements.inputs.count"],
                    }
                ]
            }
        elif schema is WebsiteUnderstanding:
            data = {
                "summary": "The catalog loaded and one search input was observed.",
                "requirement_evidence": [
                    {
                        "requirement_id": "REQ-01",
                        "support": "SUPPORTED",
                        "evidence_references": [
                            "page.navigation_status",
                            "elements.inputs.count",
                        ],
                        "missing_evidence": [],
                    }
                ],
                "observed_element_references": ["elements.inputs.count"],
            }
        elif schema is QATestCaseSet:
            data = {
                "test_cases": [
                    {
                        "test_case_id": "TC-01",
                        "title": "Inspect catalog search input",
                        "requirement_id": "REQ-01",
                        "description": "Confirm the catalog search input is present.",
                        "preconditions": ["The catalog page has loaded."],
                        "steps": ["Inspect the catalog page."],
                        "expected_result": "A search input is visible.",
                        "priority": "P1",
                        "test_type": "PAGE_LOAD",
                        "evidence_requirements": ["page.navigation_status"],
                        "validation_criteria": {"kind": "PAGE_LOAD"},
                        "depends_on": [],
                    }
                ]
            }
        elif schema is BugFindingSet:
            if any(
                marker in prompt
                for marker in (
                    "deliberately unknown optional page",
                    "transient network failure",
                    "health endpoint",
                    "catalog page loaded successfully",
                    "Page navigation returned a successful HTTP status",
                )
            ):
                data = {"findings": []}
            else:
                if "uncaught application JavaScript error" in prompt:
                    severity = Severity.MEDIUM
                    title = "Catalog rendering error"
                    root = "JavaScript failed during rendering."
                    evidence = "console.errors.count"
                elif "secondary catalog help link" in prompt:
                    severity = Severity.LOW
                    title = "Help link destination is incorrect"
                    root = "The link points to an incorrect destination."
                    evidence = "elements.links.count"
                elif "primary public landing page" in prompt:
                    severity = Severity.CRITICAL
                    title = "Primary page unavailable"
                    root = "The service is unavailable."
                    evidence = "page.response_status"
                else:
                    severity = Severity.HIGH
                    title = "Catalog server error"
                    root = "The server request returned an error."
                    evidence = "page.response_status"
                data = {
                    "findings": [
                        {
                            "bug_id": "BUG-01",
                            "title": title,
                            "description": "The observed request failed.",
                            "severity": severity.value,
                            "confidence_score": 0.9,
                            "probable_root_cause": root,
                            "supporting_evidence": [evidence],
                            "affected_url": None,
                            "recommended_action": "Review the request handling.",
                            "historical_references": [],
                        }
                    ]
                }
        elif schema is ReportNarrative:
            data = {
                "summary": "The catalog request returned HTTP 500.",
                "recommendations": ["Review server request handling."],
            }
        else:
            raise AssertionError(f"Unexpected response schema: {schema.__name__}")
        return schema.model_validate(data)


def test_bug_prompt_constrains_historical_reference_ids() -> None:
    prompt = bug_analysis_prompt(
        [],
        {},
        "Untrusted historical context.",
        {"benchmark:known-reference"},
    )
    assert '"benchmark:known-reference"' in prompt
    assert "do not infer IDs from historical context" in prompt


def test_versioned_benchmark_dataset_loads_and_covers_all_agents() -> None:
    dataset = load_dataset("qa_synthetic_v1")
    assert dataset.synthetic is True
    assert dataset.version == "1.0.0"
    assert {
        sample.agent for sample in dataset.samples
    } == set(EvaluationAgent)
    assert len(list_datasets()) == 1


def test_dataset_path_traversal_and_invalid_sample_selection_are_rejected() -> None:
    with pytest.raises(ValueError):
        load_dataset("..")
    with pytest.raises(ValueError, match="absent"):
        get_dataset_samples(
            "qa_synthetic_v1",
            EvaluationAgent.REQUIREMENT_ANALYSIS,
            ["not-a-real-sample"],
        )


def test_dataset_duplicate_sample_ids_are_rejected(tmp_path: Path, monkeypatch) -> None:
    from app.evaluation import datasets

    content = {
        "dataset_id": "duplicate_ids",
        "version": "1.0.0",
        "name": "Duplicate sample test",
        "description": "Synthetic validator fixture.",
        "created_at": "2026-11-09T00:00:00Z",
        "synthetic": True,
        "samples": [
            {
                "sample_id": "same",
                "agent": "requirement_analysis",
                "inputs": {"requirements": "Test a thing."},
                "ground_truth": {"required_terms": ["thing"]},
            },
            {
                "sample_id": "same",
                "agent": "requirement_analysis",
                "inputs": {"requirements": "Test another thing."},
                "ground_truth": {"required_terms": ["another"]},
            },
        ],
    }
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()
    (dataset_dir / "duplicate_ids.json").write_text(
        __import__("json").dumps(content),
        encoding="utf-8",
    )
    monkeypatch.setattr(datasets, "DATASET_DIR", dataset_dir)
    datasets.load_dataset.cache_clear()
    with pytest.raises(ValueError, match="invalid"):
        datasets.load_dataset("duplicate_ids")
    datasets.load_dataset.cache_clear()


def test_binary_classification_metrics_match_hand_calculation() -> None:
    metrics = binary_classification_metrics(
        [True, False, True, False],
        [True, True, False, False],
    )
    assert metrics["true_positive"] == 1
    assert metrics["false_positive"] == 1
    assert metrics["true_negative"] == 1
    assert metrics["false_negative"] == 1
    assert metrics["accuracy"] == 0.5
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5


def test_multiclass_metrics_and_zero_division_are_defined() -> None:
    metrics = classification_metrics(
        ["HIGH", "LOW", "INFO"],
        ["HIGH", "HIGH", "INFO"],
        labels=["CRITICAL", "HIGH", "LOW", "INFO"],
    )
    assert metrics["accuracy"] == pytest.approx(2 / 3)
    assert metrics["per_class"]["CRITICAL"]["precision"] == 0
    assert metrics["per_class"]["LOW"]["recall"] == 0
    assert 0 <= metrics["macro_f1"] <= 1
    assert len(metrics["confusion_matrix"]) == 4


def test_test_generation_metrics_use_explicit_denominators() -> None:
    metrics = calculate_test_generation_metrics(
        expected_requirements={"REQ-01", "REQ-02"},
        covered_requirements={"REQ-01"},
        expected_scenarios={"search", "filter"},
        generated_scenarios={"search"},
        generated_count=4,
        relevant_generated_count=3,
        duplicate_count=1,
        unsupported_count=2,
    )
    assert metrics["requirement_coverage"] == 0.5
    assert metrics["test_case_precision"] == 0.75
    assert metrics["test_case_recall"] == 0.5
    assert metrics["duplicate_rate"] == 0.25
    assert metrics["unsupported_test_rate"] == 0.5


def test_retrieval_metrics_match_hand_calculation() -> None:
    metrics = retrieval_metrics(
        {"doc-a", "doc-c"},
        ["doc-b", "doc-a", "doc-c"],
        k=3,
        relevance_grades={"doc-a": 3, "doc-c": 2},
    )
    assert metrics["precision_at_k"] == pytest.approx(2 / 3)
    assert metrics["recall_at_k"] == 1
    assert metrics["hit_rate_at_k"] == 1
    assert metrics["mean_reciprocal_rank"] == 0.5
    assert metrics["ndcg_at_k"] == pytest.approx(
        (7 / math.log2(3) + 3 / math.log2(4))
        / (7 + 3 / math.log2(3))
    )


def test_metric_edge_cases_are_explicit() -> None:
    no_predictions = binary_classification_metrics([False], [False])
    assert no_predictions["precision"] == 0
    assert no_predictions["recall"] == 0
    assert retrieval_metrics(set(), [], k=5)["recall_at_k"] == 0
    with pytest.raises(ValueError, match="K"):
        retrieval_metrics(set(), [], k=0)


@pytest.mark.parametrize(
    "agent",
    [
        EvaluationAgent.REQUIREMENT_ANALYSIS,
        EvaluationAgent.PLANNING,
        EvaluationAgent.WEBSITE_UNDERSTANDING,
        EvaluationAgent.TEST_GENERATION,
        EvaluationAgent.BUG_ANALYSIS,
        EvaluationAgent.REPORTING,
        EvaluationAgent.WORKFLOW,
    ],
)
def test_agent_evaluations_are_mockable_and_persist_without_qa_mutation(
    db_session,
    agent: EvaluationAgent,
) -> None:
    _, samples = get_dataset_samples("qa_synthetic_v1", agent)
    request = EvaluationRunRequest(
        dataset_id="qa_synthetic_v1",
        agent=agent,
        sample_ids=[samples[0].sample_id],
        provider_mode="mock",
        prompt_version="test-fixture",
        approval_confirmed=agent is EvaluationAgent.WORKFLOW,
    )
    runner = EvaluationRunner(mock_provider=DatasetMockProvider())
    response = runner.run(db_session, request)
    assert response.status == "completed", response.sample_results
    assert response.completed_samples == 1
    assert response.failed_samples == 0
    assert response.skipped_samples == 0
    assert response.sample_results[0].status == "completed"
    assert "Mock-provider" in " ".join(response.limitations)
    persisted = EvaluationService.get(db_session, response.id)
    assert persisted is not None
    assert persisted.id == response.id


def test_bug_analysis_metrics_include_detection_and_severity(db_session) -> None:
    request = EvaluationRunRequest(
        dataset_id="qa_synthetic_v1",
        agent=EvaluationAgent.BUG_ANALYSIS,
        provider_mode="mock",
    )
    response = EvaluationRunner(
        mock_provider=DatasetMockProvider()
    ).run(db_session, request)
    detection = response.metrics["bug_detection"]
    severity = response.metrics["severity_classification"]
    assert detection["true_positive"] == 4
    assert detection["false_positive"] == 0
    assert detection["true_negative"] == 3
    assert detection["false_negative"] == 0
    assert severity["accuracy"] == 1
    assert set(severity["labels"]) == {
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "LOW",
        "INFO",
    }


def test_api_lists_datasets_and_metrics(client) -> None:
    datasets_response = client.get("/api/v1/evaluations/datasets")
    metrics_response = client.get("/api/v1/evaluations/metrics")
    assert datasets_response.status_code == 200
    assert datasets_response.json()[0]["synthetic"] is True
    assert metrics_response.status_code == 200
    assert "precision_at_k" in {item["name"] for item in metrics_response.json()}


def test_api_evaluation_run_list_report_and_comparison(client) -> None:
    service = EvaluationService(
        EvaluationRunner(mock_provider=DatasetMockProvider())
    )
    app.dependency_overrides[get_evaluation_service] = lambda: service
    try:
        payload = {
            "dataset_id": "qa_synthetic_v1",
            "agent": "requirement_analysis",
            "sample_ids": ["requirements-search-01"],
            "provider_mode": "mock",
        }
        baseline = client.post("/api/v1/evaluations/run", json=payload)
        candidate = client.post("/api/v1/evaluations/run", json=payload)
        assert baseline.status_code == 201
        assert candidate.status_code == 201
        baseline_id = baseline.json()["id"]
        candidate_id = candidate.json()["id"]
        assert client.get(f"/api/v1/evaluations/{baseline_id}").status_code == 200
        assert client.get(
            f"/api/v1/evaluations/{baseline_id}/report"
        ).status_code == 200
        assert client.get("/api/v1/evaluations").json()["total"] >= 2
        comparison = client.post(
            "/api/v1/evaluations/compare",
            json={"baseline_id": baseline_id, "candidate_id": candidate_id},
        )
        assert comparison.status_code == 200
        assert comparison.json()["comparable"] is True
    finally:
        app.dependency_overrides.pop(get_evaluation_service, None)


def test_api_rejects_unknown_dataset(client) -> None:
    response = client.post(
        "/api/v1/evaluations/run",
        json={
            "dataset_id": "missing_dataset",
            "agent": "requirement_analysis",
            "provider_mode": "mock",
        },
    )
    assert response.status_code == 404


class FixedEmbeddings:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        normalized = text.casefold()
        if "checkout" in normalized or "shipping" in normalized or "stale" in normalized:
            return [1.0, 0.0, 0.0]
        if "catalog" in normalized or "image" in normalized:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def document_chunks(self, *, project_id: str, document_id: str):
        return [
            {
                "chunk_id": chunk_id,
                "content": item["content"],
                "metadata": item["metadata"],
            }
            for chunk_id, item in self.records.items()
            if item["metadata"]["project_id"] == project_id
            and item["metadata"]["document_id"] == document_id
        ]

    def upsert(self, chunks, embeddings) -> None:
        for chunk, vector in zip(chunks, embeddings, strict=True):
            self.records[chunk["chunk_id"]] = {
                "content": chunk["content"],
                "metadata": chunk["metadata"],
                "vector": vector,
            }

    def delete_chunks(self, ids: list[str]) -> None:
        for chunk_id in ids:
            self.records.pop(chunk_id, None)

    def search(self, query_embedding, *, top_k: int, where):
        project_id = where.get("project_id")
        if project_id is None and "$and" in where:
            project_id = next(
                item["project_id"]
                for item in where["$and"]
                if "project_id" in item
            )
        hits = []
        for chunk_id, item in self.records.items():
            metadata = item["metadata"]
            if metadata["project_id"] != project_id:
                continue
            score = sum(
                left * right
                for left, right in zip(query_embedding, item["vector"], strict=True)
            )
            hits.append(
                {
                    "chunk_id": chunk_id,
                    "content": item["content"],
                    "metadata": metadata,
                    "distance": 1.0 - score,
                }
            )
        return sorted(hits, key=lambda hit: hit["distance"])[:top_k]


def test_rag_runner_uses_controlled_docs_and_project_scoped_retrieval(
    db_session,
    monkeypatch,
) -> None:
    from app.evaluation import runner as runner_module

    fake_store = InMemoryVectorStore()
    monkeypatch.setattr(
        runner_module,
        "get_embedding_service",
        lambda *_args: FixedEmbeddings(),
    )
    monkeypatch.setattr(
        runner_module,
        "ChromaVectorStore",
        lambda *_args, **_kwargs: fake_store,
    )
    response = EvaluationRunner().run(
        db_session,
        EvaluationRunRequest(
            dataset_id="qa_synthetic_v1",
            agent=EvaluationAgent.RAG_RETRIEVAL,
            provider_mode="live",
        ),
    )
    assert response.status == "completed"
    assert response.metrics["precision_at_k"] == pytest.approx(1 / 3)
    assert response.metrics["recall_at_k"] == 1
    assert response.metrics["mean_reciprocal_rank"] == 1
    assert response.metrics["project_scope_isolated"] is True
    assert response.metrics["source_reference_preserved"] is True
