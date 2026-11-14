import hashlib
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies import get_knowledge_service
from app.models.execution import Execution
from app.rag.schemas import (
    KnowledgeDocumentDetail,
    KnowledgeHealthResponse,
    KnowledgeIngestRequest,
    KnowledgeIngestResponse,
    KnowledgeListResponse,
    KnowledgeSearchRequest,
    KnowledgeSourceType,
    RetrievedKnowledge,
)
from app.rag.service import KnowledgeService
from app.rag.vector_store import VectorStoreUnavailableError
from app.schemas.qa import HistoricalBugMatch

logger = logging.getLogger(__name__)
router = APIRouter()


def _unavailable(exc: Exception) -> HTTPException:
    logger.warning("Knowledge service unavailable (%s)", type(exc).__name__)
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Knowledge storage or local embedding service is unavailable.",
    )


@router.post(
    "/knowledge/ingest",
    response_model=KnowledgeIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a persisted QA report or authorized text document",
)
def ingest_knowledge(
    payload: KnowledgeIngestRequest,
    session: Session = Depends(get_db),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeIngestResponse:
    try:
        service.ensure_project(session, payload.project_id)
        if payload.execution_id is not None:
            documents = service.ingest_execution(
                session,
                project_id=payload.project_id,
                execution_id=payload.execution_id,
            )
        else:
            if payload.file_type and payload.file_type.lower().lstrip(".") == "json":
                try:
                    json.loads(payload.content or "")
                except json.JSONDecodeError as exc:
                    raise ValueError("JSON knowledge documents must contain valid JSON.") from exc
            reference = payload.source_reference or (
                "document:" + hashlib.sha256(
                    (payload.content or "").encode("utf-8")
                ).hexdigest()
            )
            summary = service.ingest_text(
                content=payload.content or "",
                title=payload.title or "Testing knowledge document",
                project_id=payload.project_id,
                source_type=KnowledgeSourceType.TESTING_DOCUMENT,
                source_reference=reference,
            )
            documents = [summary]
        return KnowledgeIngestResponse(documents=documents)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, VectorStoreUnavailableError, RuntimeError) as exc:
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        raise _unavailable(exc) from exc


@router.get(
    "/knowledge",
    response_model=KnowledgeListResponse,
    summary="List project-scoped knowledge metadata",
)
def list_knowledge(
    project_id: UUID,
    authorization_confirmed: bool,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeListResponse:
    if not authorization_confirmed:
        raise HTTPException(status_code=403, detail="Project authorization is required.")
    try:
        items, total = service.list_documents(
            project_id=project_id,
            offset=offset,
            limit=limit,
        )
    except Exception as exc:
        raise _unavailable(exc) from exc
    next_offset = offset + len(items) if offset + len(items) < total else None
    return KnowledgeListResponse(items=items, next_offset=next_offset)


@router.get(
    "/knowledge/health",
    response_model=KnowledgeHealthResponse,
    summary="Check knowledge storage and local embedding readiness",
)
def knowledge_health(
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeHealthResponse:
    settings = service.settings
    if not settings.rag_enabled:
        return KnowledgeHealthResponse(
            enabled=False,
            available=False,
            embedding_model=settings.rag_embedding_model,
            collection_name=settings.chroma_collection_name,
        )
    try:
        service.health()
        service.embeddings.embed_query("knowledge health check")
        return KnowledgeHealthResponse(
            enabled=True,
            available=True,
            embedding_model=settings.rag_embedding_model,
            collection_name=settings.chroma_collection_name,
        )
    except Exception as exc:
        logger.warning("Knowledge health check failed (%s)", type(exc).__name__)
        return KnowledgeHealthResponse(
            enabled=True,
            available=False,
            embedding_model=settings.rag_embedding_model,
            collection_name=settings.chroma_collection_name,
            error_category=type(exc).__name__,
        )


@router.post(
    "/knowledge/search",
    response_model=list[RetrievedKnowledge],
    summary="Search project-scoped historical knowledge",
)
def search_knowledge(
    payload: KnowledgeSearchRequest,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> list[RetrievedKnowledge]:
    try:
        return service.search(
            payload.query,
            project_id=payload.project_id,
            top_k=payload.top_k,
            source_type=payload.source_type,
            severity=payload.severity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise _unavailable(exc) from exc


@router.get(
    "/knowledge/{document_id}",
    response_model=KnowledgeDocumentDetail,
    summary="Get sanitized project-scoped knowledge content",
)
def get_knowledge(
    document_id: str,
    project_id: UUID,
    authorization_confirmed: bool,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeDocumentDetail:
    if not authorization_confirmed:
        raise HTTPException(status_code=403, detail="Project authorization is required.")
    try:
        document = service.get_document(document_id, project_id=project_id)
    except Exception as exc:
        raise _unavailable(exc) from exc
    if document is None:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")
    return KnowledgeDocumentDetail.model_validate(document)


@router.delete(
    "/knowledge/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete vector knowledge without deleting its source QA data",
)
def delete_knowledge(
    document_id: str,
    project_id: UUID,
    authorization_confirmed: bool,
    service: KnowledgeService = Depends(get_knowledge_service),
) -> None:
    if not authorization_confirmed:
        raise HTTPException(status_code=403, detail="Project authorization is required.")
    try:
        deleted = service.delete_document(document_id, project_id=project_id)
    except Exception as exc:
        raise _unavailable(exc) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Knowledge document not found.")


@router.get(
    "/executions/{execution_id}/historical-bugs",
    response_model=list[HistoricalBugMatch],
    summary="Find project-scoped similar historical findings",
)
def historical_bugs(
    execution_id: UUID,
    authorization_confirmed: bool,
    session: Session = Depends(get_db),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> list[HistoricalBugMatch]:
    if not authorization_confirmed:
        raise HTTPException(status_code=403, detail="Project authorization is required.")
    execution = session.get(Execution, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found.")
    report = execution.qa_report or {}
    findings = report.get("findings", [])
    inspection = execution.inspection_result or {}
    query = " ".join(
        str(value)
        for finding in findings
        if isinstance(finding, dict)
        for value in (finding.get("title"), finding.get("description"))
        if value
    )
    if not query:
        query = json.dumps(
            inspection.get("events", {}),
            ensure_ascii=True,
            default=str,
        )
    try:
        matches = service.historical_bug_matches(
            query,
            project_id=execution.project_id,
        ) if query.strip() else []
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise _unavailable(exc) from exc
    return matches
