from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvaluationAgent(StrEnum):
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    PLANNING = "planning"
    WEBSITE_UNDERSTANDING = "website_understanding"
    TEST_GENERATION = "test_generation"
    BUG_ANALYSIS = "bug_analysis"
    REPORTING = "reporting"
    RAG_RETRIEVAL = "rag_retrieval"
    WORKFLOW = "workflow"


class DatasetSample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_id: str = Field(min_length=1, max_length=100)
    agent: EvaluationAgent
    inputs: dict[str, Any]
    ground_truth: dict[str, Any] = Field(min_length=1)


class EvaluationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1000)
    created_at: datetime
    synthetic: bool
    samples: list[DatasetSample] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def samples_are_unique(self) -> "EvaluationDataset":
        ids = [sample.sample_id for sample in self.samples]
        if len(ids) != len(set(ids)):
            raise ValueError("Dataset sample identifiers must be unique.")
        return self


class EvaluationRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    agent: EvaluationAgent
    sample_ids: list[str] | None = Field(default=None, max_length=100)
    repeat_count: int = Field(default=1, ge=1, le=5)
    provider_mode: str = Field(default="live", pattern=r"^(live|mock)$")
    model_identifier: str | None = Field(default=None, min_length=1, max_length=120)
    prompt_version: str = Field(default="current", min_length=1, max_length=80)
    rag_enabled: bool = False
    approval_confirmed: bool = False

    @model_validator(mode="after")
    def sample_ids_are_unique(self) -> "EvaluationRunRequest":
        if self.sample_ids is not None and len(self.sample_ids) != len(set(self.sample_ids)):
            raise ValueError("Requested sample identifiers must be unique.")
        if self.agent is EvaluationAgent.RAG_RETRIEVAL and self.provider_mode == "mock":
            raise ValueError("RAG retrieval uses the configured local embedding model, not an LLM mock.")
        if self.agent is EvaluationAgent.RAG_RETRIEVAL and self.model_identifier:
            raise ValueError("Use RAG_EMBEDDING_MODEL to select the retrieval embedding model.")
        if self.agent is EvaluationAgent.WORKFLOW and not self.approval_confirmed:
            raise ValueError(
                "Workflow benchmark runs require explicit approval confirmation for the synthetic inspection and test-plan gates."
            )
        return self


class EvaluationComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_id: UUID
    candidate_id: UUID


class EvaluationDatasetSummary(BaseModel):
    dataset_id: str
    version: str
    name: str
    description: str
    synthetic: bool
    sample_count: int
    agents: list[EvaluationAgent]


class EvaluationSampleResult(BaseModel):
    sample_id: str
    run_number: int = Field(ge=1)
    status: str
    duration_ms: float = Field(ge=0)
    metrics: dict[str, Any] = Field(default_factory=dict)
    error_category: str | None = None


class EvaluationExperimentResponse(BaseModel):
    id: UUID
    experiment_name: str
    dataset_id: str
    dataset_version: str
    agent: EvaluationAgent
    provider_mode: str
    provider_name: str
    model_identifier: str
    prompt_version: str
    rag_enabled: bool
    status: str
    configuration: dict[str, Any]
    metrics: dict[str, Any]
    sample_results: list[EvaluationSampleResult]
    total_samples: int
    completed_samples: int
    failed_samples: int
    skipped_samples: int
    run_count: int
    duration_ms: float
    created_at: datetime
    limitations: list[str] = Field(default_factory=list)


class EvaluationExperimentListResponse(BaseModel):
    items: list[EvaluationExperimentResponse]
    total: int
    page: int
    page_size: int


class EvaluationMetricInfo(BaseModel):
    name: str
    description: str
    formula: str
    interpretation: str


class EvaluationComparisonResponse(BaseModel):
    baseline_id: UUID
    candidate_id: UUID
    dataset_id: str
    dataset_version: str
    agent: EvaluationAgent
    metric_deltas: dict[str, float | None]
    comparable: bool
    limitations: list[str] = Field(default_factory=list)
