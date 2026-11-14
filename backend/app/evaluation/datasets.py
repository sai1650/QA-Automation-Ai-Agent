import json
from functools import lru_cache
from pathlib import Path

from app.evaluation.schemas import (
    EvaluationAgent,
    EvaluationDataset,
    EvaluationDatasetSummary,
    DatasetSample,
)
from app.rag.schemas import KnowledgeSourceType
from app.schemas.finding import Severity

DATASET_DIR = Path(__file__).resolve().parent / "datasets"


def _dataset_path(dataset_id: str) -> Path:
    if not dataset_id.isascii() or not dataset_id.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Invalid dataset identifier.")
    candidate = (DATASET_DIR / f"{dataset_id}.json").resolve()
    if candidate.parent != DATASET_DIR.resolve():
        raise ValueError("Dataset path is outside the approved dataset directory.")
    return candidate


@lru_cache(maxsize=32)
def load_dataset(dataset_id: str) -> EvaluationDataset:
    path = _dataset_path(dataset_id)
    if not path.is_file():
        raise LookupError("Evaluation dataset not found.")
    try:
        if path.stat().st_size > 1_000_000:
            raise ValueError("Evaluation dataset exceeds the approved size limit.")
        raw = json.loads(path.read_text(encoding="utf-8"))
        dataset = EvaluationDataset.model_validate(raw)
        _validate_samples(dataset)
    except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
        raise ValueError("Evaluation dataset is invalid.") from exc
    if dataset.dataset_id != dataset_id:
        raise ValueError("Dataset identifier does not match its approved filename.")
    return dataset


def _validate_samples(dataset: EvaluationDataset) -> None:
    required_inputs = {
        EvaluationAgent.REQUIREMENT_ANALYSIS: {"requirements"},
        EvaluationAgent.PLANNING: {"analysis"},
        EvaluationAgent.WEBSITE_UNDERSTANDING: {"analysis", "evidence_index"},
        EvaluationAgent.TEST_GENERATION: {
            "analysis",
            "plan",
            "understanding",
            "evidence_index",
        },
        EvaluationAgent.BUG_ANALYSIS: {"execution_results", "evidence_index"},
        EvaluationAgent.REPORTING: {
            "execution_id",
            "tests",
            "results",
            "findings",
        },
        EvaluationAgent.RAG_RETRIEVAL: {
            "query",
            "top_k",
            "project_scope",
            "documents",
        },
        EvaluationAgent.WORKFLOW: {
            "requirements",
            "evidence_index",
            "inspection",
            "execution_results",
            "execution_id",
        },
    }
    for sample in dataset.samples:
        if not required_inputs[sample.agent] <= sample.inputs.keys():
            raise ValueError(f"Dataset sample {sample.sample_id} is missing required inputs.")
        if sample.agent is EvaluationAgent.BUG_ANALYSIS:
            if not isinstance(sample.ground_truth.get("is_bug"), bool):
                raise ValueError("Bug benchmark cases require a boolean is_bug label.")
            if sample.ground_truth.get("severity") not in {item.value for item in Severity}:
                raise ValueError("Bug benchmark severity is not a supported label.")
        if sample.agent is EvaluationAgent.RAG_RETRIEVAL:
            documents = sample.inputs["documents"]
            ids = [document["document_id"] for document in documents]
            references = [document["source_reference"] for document in documents]
            if len(ids) != len(set(ids)) or len(references) != len(set(references)):
                raise ValueError("RAG benchmark document identifiers must be unique.")
            for document in documents:
                KnowledgeSourceType(document["source_type"])
            if not set(sample.ground_truth["relevant_document_ids"]) <= set(ids):
                raise ValueError("RAG relevance judgments reference unknown documents.")
            if not 1 <= int(sample.ground_truth["k"]) <= int(sample.inputs["top_k"]):
                raise ValueError("RAG benchmark K is outside the configured retrieval range.")


def list_datasets() -> list[EvaluationDatasetSummary]:
    summaries: list[EvaluationDatasetSummary] = []
    for path in sorted(DATASET_DIR.glob("*.json")):
        dataset = load_dataset(path.stem)
        summaries.append(
            EvaluationDatasetSummary(
                dataset_id=dataset.dataset_id,
                version=dataset.version,
                name=dataset.name,
                description=dataset.description,
                synthetic=dataset.synthetic,
                sample_count=len(dataset.samples),
                agents=sorted({sample.agent for sample in dataset.samples}),
            )
        )
    return summaries


def get_dataset_samples(
    dataset_id: str,
    agent: EvaluationAgent,
    sample_ids: list[str] | None = None,
) -> tuple[EvaluationDataset, list[DatasetSample]]:
    dataset = load_dataset(dataset_id)
    available = [sample for sample in dataset.samples if sample.agent is agent]
    if sample_ids is not None:
        requested = set(sample_ids)
        found = {sample.sample_id for sample in available}
        if requested - found:
            raise ValueError("Requested samples are absent from this dataset and agent.")
        available = [sample for sample in available if sample.sample_id in requested]
    if not available:
        raise ValueError("Dataset contains no samples for the selected agent.")
    return dataset, available
