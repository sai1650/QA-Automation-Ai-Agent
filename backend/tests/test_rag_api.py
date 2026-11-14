from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.dependencies import get_knowledge_service
from app.models.execution import Execution, ExecutionStatus
from app.rag.service import KnowledgeService
from tests.test_projects import create_project
from tests.test_rag import DeterministicEmbeddings, MemoryVectorStore


def _service(monkeypatch: Any) -> KnowledgeService:
    settings = type(
        "TestSettings",
        (),
        {
            "rag_embedding_model": "test-deterministic",
            "rag_embedding_device": "cpu",
            "rag_chunk_size": 800,
            "rag_chunk_overlap": 120,
            "rag_max_chunks_per_document": 50,
            "rag_max_document_chars": 100000,
            "rag_min_relevance_score": 0.35,
            "rag_top_k": 5,
            "rag_max_context_chars": 6000,
            "chroma_persist_path": Path("."),
            "chroma_collection_name": "test",
            "rag_enabled": True,
        },
    )()
    monkeypatch.setattr("app.rag.service.get_settings", lambda: settings)
    return KnowledgeService(
        embeddings=DeterministicEmbeddings(),
        vector_store=MemoryVectorStore(),
    )


def test_knowledge_apis_ingest_search_list_detail_and_delete(
    client: TestClient,
    monkeypatch: Any,
) -> None:
    service = _service(monkeypatch)
    app = client.app
    app.dependency_overrides[get_knowledge_service] = lambda: service
    try:
        project = create_project(client)
        project_id = project["id"]
        response = client.post(
            "/api/v1/knowledge/ingest",
            json={
                "project_id": project_id,
                "authorization_confirmed": True,
                "title": "Timeout guide",
                "file_type": "md",
                "source_reference": "docs:timeouts",
                "content": (
                    "Timeout failures should be diagnosed with request timing "
                    "and server logs. token=supersecret"
                ),
            },
        )
        assert response.status_code == 201
        document_id = response.json()["documents"][0]["document_id"]

        listed = client.get(
            "/api/v1/knowledge",
            params={
                "project_id": project_id,
                "authorization_confirmed": "true",
            },
        )
        assert listed.status_code == 200
        assert listed.json()["items"][0]["document_id"] == document_id

        detail = client.get(
            f"/api/v1/knowledge/{document_id}",
            params={
                "project_id": project_id,
                "authorization_confirmed": "true",
            },
        )
        assert detail.status_code == 200
        assert "Timeout failures" in detail.json()["content"]
        assert "supersecret" not in detail.json()["content"]

        health = client.get("/api/v1/knowledge/health")
        assert health.status_code == 200
        assert health.json()["available"] is True

        assert "/api/v1/knowledge/search" in client.get("/openapi.json").json()["paths"]
        invalid = client.post(
            "/api/v1/knowledge/ingest",
            json={
                "project_id": project_id,
                "authorization_confirmed": True,
                "title": "Unsupported",
                "file_type": "pdf",
                "content": "This file format is intentionally unsupported.",
            },
        )
        assert invalid.status_code == 422

        search = client.post(
            "/api/v1/knowledge/search",
            json={
                "project_id": project_id,
                "authorization_confirmed": True,
                "query": "timeout",
            },
        )
        assert search.status_code == 200
        assert search.json()[0]["source_reference"] == "docs:timeouts"

        denied = client.get(
            "/api/v1/knowledge",
            params={"project_id": project_id, "authorization_confirmed": "false"},
        )
        assert denied.status_code == 403

        deleted = client.delete(
            f"/api/v1/knowledge/{document_id}",
            params={
                "project_id": project_id,
                "authorization_confirmed": "true",
            },
        )
        assert deleted.status_code == 204
        assert client.get(
            f"/api/v1/knowledge/{document_id}",
            params={
                "project_id": project_id,
                "authorization_confirmed": "true",
            },
        ).status_code == 404
    finally:
        app.dependency_overrides.pop(get_knowledge_service, None)


def test_ingestion_uses_only_persisted_execution_report_and_historical_refs(
    client: TestClient,
    db_session: Session,
    monkeypatch: Any,
) -> None:
    service = _service(monkeypatch)
    app = client.app
    app.dependency_overrides[get_knowledge_service] = lambda: service
    try:
        project = create_project(client, name="Historical QA project")
        project_id = UUID(project["id"])
        execution = Execution(
            project_id=project_id,
            status=ExecutionStatus.COMPLETED,
            requirements="Investigate a page timeout.",
            qa_report={
                "summary": "The page returned a timeout.",
                "findings": [
                    {
                        "bug_id": "BUG-01",
                        "title": "Request timeout",
                        "description": "The page request timed out.",
                        "severity": "HIGH",
                        "probable_root_cause": "Upstream response delay.",
                        "supporting_evidence": ["page.navigation_status"],
                        "recommended_action": "Inspect service timing.",
                    }
                ],
                "recommendations": ["Review server-side request timing."],
            },
        )
        db_session.add(execution)
        db_session.commit()
        db_session.refresh(execution)

        response = client.post(
            "/api/v1/knowledge/ingest",
            json={
                "project_id": str(project_id),
                "execution_id": str(execution.id),
                "authorization_confirmed": True,
            },
        )
        assert response.status_code == 201
        assert len(response.json()["documents"]) == 2
        assert {
            item["source_type"] for item in response.json()["documents"]
        } == {"historical_bug", "qa_report"}

        matches = client.get(
            f"/api/v1/executions/{execution.id}/historical-bugs",
            params={"authorization_confirmed": "true"},
        )
        assert matches.status_code == 200
        assert matches.json()[0]["source_reference"] == (
            f"execution:{execution.id}/bug:BUG-01"
        )
    finally:
        app.dependency_overrides.pop(get_knowledge_service, None)
