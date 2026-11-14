from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.evaluation.runner import EvaluationRunner
from app.evaluation.schemas import (
    EvaluationAgent,
    EvaluationExperimentListResponse,
    EvaluationExperimentResponse,
    EvaluationRunRequest,
)
from app.models.evaluation import EvaluationExperiment


class EvaluationService:
    def __init__(self, runner: EvaluationRunner | None = None) -> None:
        self.runner = runner or EvaluationRunner()

    def run(
        self,
        session: Session,
        request: EvaluationRunRequest,
    ) -> EvaluationExperimentResponse:
        return self.runner.run(session, request)

    @staticmethod
    def get(
        session: Session,
        evaluation_id: UUID,
    ) -> EvaluationExperimentResponse | None:
        record = session.get(EvaluationExperiment, evaluation_id)
        return EvaluationRunner.to_response(record) if record is not None else None

    @staticmethod
    def list(
        session: Session,
        *,
        offset: int,
        limit: int,
        dataset_id: str | None = None,
        agent: EvaluationAgent | None = None,
    ) -> EvaluationExperimentListResponse:
        query = select(EvaluationExperiment)
        count_query = select(func.count()).select_from(EvaluationExperiment)
        if dataset_id is not None:
            query = query.where(EvaluationExperiment.dataset_id == dataset_id)
            count_query = count_query.where(
                EvaluationExperiment.dataset_id == dataset_id
            )
        if agent is not None:
            query = query.where(EvaluationExperiment.agent_name == agent.value)
            count_query = count_query.where(
                EvaluationExperiment.agent_name == agent.value
            )
        total = session.scalar(count_query) or 0
        records = session.scalars(
            query.order_by(EvaluationExperiment.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return EvaluationExperimentListResponse(
            items=[EvaluationRunner.to_response(record) for record in records],
            total=total,
            page=offset // limit + 1,
            page_size=limit,
        )

    @staticmethod
    def compare(
        session: Session,
        baseline_id: UUID,
        candidate_id: UUID,
    ) -> dict[str, object] | None:
        baseline = session.get(EvaluationExperiment, baseline_id)
        candidate = session.get(EvaluationExperiment, candidate_id)
        if baseline is None or candidate is None:
            return None
        comparable = (
            baseline.dataset_id == candidate.dataset_id
            and baseline.dataset_version == candidate.dataset_version
            and baseline.agent_name == candidate.agent_name
            and baseline.configuration.get("sample_ids")
            == candidate.configuration.get("sample_ids")
        )
        deltas: dict[str, float | None] = {}
        config_fields = (
            "provider_name",
            "model_identifier",
            "prompt_version",
            "rag_enabled",
            "repeat_count",
        )
        differing_config = [
            field
            for field in config_fields
            if baseline.configuration.get(field) != candidate.configuration.get(field)
        ]
        if comparable:
            baseline_values = _flatten_numbers(baseline.metrics)
            candidate_values = _flatten_numbers(candidate.metrics)
            for key in sorted(set(baseline_values) & set(candidate_values)):
                deltas[key] = candidate_values[key] - baseline_values[key]
        return {
            "baseline_id": baseline.id,
            "candidate_id": candidate.id,
            "dataset_id": candidate.dataset_id,
            "dataset_version": candidate.dataset_version,
            "agent": EvaluationAgent(candidate.agent_name),
            "metric_deltas": deltas,
            "comparable": comparable,
            "limitations": (
                [
                    "Runs use different provider/model/prompt/RAG/repeat configuration fields: "
                    + ", ".join(differing_config)
                    + "; observed deltas are not causal evidence."
                ]
                if comparable and differing_config
                else []
            )
            if comparable
            else [
                "Runs differ by dataset/version, agent, or selected sample set; metric deltas were not calculated."
            ],
        }


def _flatten_numbers(value: object, prefix: str = "") -> dict[str, float]:
    flattened: dict[str, float] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten_numbers(child, path))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        flattened[prefix] = float(value)
    return flattened
