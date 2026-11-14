import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies import get_evaluation_service
from app.evaluation.datasets import list_datasets, load_dataset
from app.evaluation.schemas import (
    EvaluationAgent,
    EvaluationComparisonRequest,
    EvaluationComparisonResponse,
    EvaluationDatasetSummary,
    EvaluationExperimentListResponse,
    EvaluationExperimentResponse,
    EvaluationMetricInfo,
    EvaluationRunRequest,
)
from app.evaluation.service import EvaluationService

logger = logging.getLogger(__name__)
router = APIRouter()

METRICS = [
    EvaluationMetricInfo(
        name="accuracy",
        description="Correct predictions divided by all predictions.",
        formula="(TP + TN) / (TP + FP + TN + FN)",
        interpretation="Higher is better; can obscure class imbalance.",
    ),
    EvaluationMetricInfo(
        name="precision",
        description="Positive predictions that are correct.",
        formula="TP / (TP + FP)",
        interpretation="Zero when there are no positive predictions.",
    ),
    EvaluationMetricInfo(
        name="recall",
        description="Actual positives correctly predicted.",
        formula="TP / (TP + FN)",
        interpretation="Zero when there are no positive ground-truth samples.",
    ),
    EvaluationMetricInfo(
        name="f1",
        description="Harmonic mean of precision and recall.",
        formula="2 * precision * recall / (precision + recall)",
        interpretation="Zero when both precision and recall are zero.",
    ),
    EvaluationMetricInfo(
        name="requirement_coverage",
        description="Expected requirements covered by generated plan/test cases.",
        formula="covered relevant requirements / expected relevant requirements",
        interpretation="Zero when no requirements were expected.",
    ),
    EvaluationMetricInfo(
        name="test_case_precision",
        description="Generated cases supported and relevant to a labeled requirement.",
        formula="relevant generated cases / generated cases",
        interpretation="Zero when no cases were generated.",
    ),
    EvaluationMetricInfo(
        name="test_case_recall",
        description="Expected scenario terms represented by generated test cases.",
        formula="matched expected scenarios / expected scenarios",
        interpretation="A deterministic lexical proxy, not a semantic human judgment.",
    ),
    EvaluationMetricInfo(
        name="precision_at_k",
        description="Relevant retrieved documents among the top K, divided by K.",
        formula="relevant retrieved @ K / K",
        interpretation="Uses dataset relevance judgments, not embedding similarity as truth.",
    ),
    EvaluationMetricInfo(
        name="recall_at_k",
        description="Relevant retrieved documents among top K, divided by all relevant.",
        formula="relevant retrieved @ K / relevant documents",
        interpretation="Zero when the benchmark has no relevant documents.",
    ),
    EvaluationMetricInfo(
        name="mean_reciprocal_rank",
        description="Reciprocal rank of the first relevant retrieved document.",
        formula="1 / rank(first relevant)",
        interpretation="Zero when no relevant document is retrieved.",
    ),
    EvaluationMetricInfo(
        name="ndcg_at_k",
        description="Normalized discounted cumulative gain through rank K.",
        formula="DCG@K / ideal DCG@K",
        interpretation="Uses explicit integer relevance grades from the dataset.",
    ),
]


@router.post(
    "/run",
    response_model=EvaluationExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run and persist a controlled AI evaluation",
)
def run_evaluation(
    payload: EvaluationRunRequest,
    session: Session = Depends(get_db),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationExperimentResponse:
    try:
        load_dataset(payload.dataset_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.provider_mode == "mock" and service.runner.mock_provider is None:
        raise HTTPException(
            status_code=422,
            detail="Mock providers are available only through explicit test injection.",
        )
    try:
        return service.run(session, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Evaluation run could not be completed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Evaluation service is unavailable. Check the configured provider and local embedding model.",
        ) from exc


@router.get(
    "",
    response_model=EvaluationExperimentListResponse,
    summary="List saved evaluation experiments",
)
def list_evaluations(
    session: Session = Depends(get_db),
    dataset_id: str | None = Query(default=None, pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$"),
    agent: EvaluationAgent | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationExperimentListResponse:
    return service.list(
        session,
        offset=(page - 1) * page_size,
        limit=page_size,
        dataset_id=dataset_id,
        agent=agent,
    )


@router.get(
    "/datasets",
    response_model=list[EvaluationDatasetSummary],
    summary="List approved versioned evaluation datasets",
)
def datasets() -> list[EvaluationDatasetSummary]:
    try:
        return list_datasets()
    except (OSError, ValueError) as exc:
        logger.exception("Evaluation dataset catalog is invalid (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="The approved evaluation dataset catalog could not be loaded.",
        ) from exc


@router.get(
    "/metrics",
    response_model=list[EvaluationMetricInfo],
    summary="List implemented metric definitions",
)
def metrics() -> list[EvaluationMetricInfo]:
    return METRICS


@router.get(
    "/{evaluation_id}",
    response_model=EvaluationExperimentResponse,
    summary="Retrieve a saved evaluation experiment",
)
def get_evaluation(
    evaluation_id: UUID,
    session: Session = Depends(get_db),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationExperimentResponse:
    response = service.get(session, evaluation_id)
    if response is None:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    return response


@router.get(
    "/{evaluation_id}/report",
    response_model=EvaluationExperimentResponse,
    summary="Retrieve the structured JSON evaluation report",
)
def get_evaluation_report(
    evaluation_id: UUID,
    session: Session = Depends(get_db),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationExperimentResponse:
    return get_evaluation(evaluation_id, session, service)


@router.post(
    "/compare",
    response_model=EvaluationComparisonResponse,
    summary="Compare two saved evaluation experiments",
)
def compare_evaluations(
    payload: EvaluationComparisonRequest,
    session: Session = Depends(get_db),
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvaluationComparisonResponse:
    result = service.compare(session, payload.baseline_id, payload.candidate_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    return EvaluationComparisonResponse.model_validate(result)
