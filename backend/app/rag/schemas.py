from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.common import CommonSchema


class KnowledgeSourceType(str, Enum):
    HISTORICAL_BUG = "historical_bug"
    QA_REPORT = "qa_report"
    TESTING_DOCUMENT = "testing_document"


class KnowledgeIngestRequest(CommonSchema):
    project_id: UUID
    authorization_confirmed: bool
    execution_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = Field(default=None, min_length=1, max_length=500000)
    file_type: str | None = Field(default=None, max_length=10)
    source_reference: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def exactly_one_input(self) -> "KnowledgeIngestRequest":
        if not self.authorization_confirmed:
            raise ValueError("Project authorization must be explicitly confirmed.")
        if (self.execution_id is None) == (self.content is None):
            raise ValueError("Provide either an execution_id or document content.")
        if self.content is not None and (
            self.file_type is None
            or self.file_type.lower().lstrip(".") not in {"md", "txt", "json"}
        ):
            raise ValueError("file_type must be md, txt, or json for text documents.")
        if self.execution_id is not None and self.file_type is not None:
            raise ValueError("file_type is only valid for explicit text documents.")
        return self


class KnowledgeSearchRequest(CommonSchema):
    project_id: UUID
    authorization_confirmed: bool
    query: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    source_type: KnowledgeSourceType | None = None
    severity: str | None = Field(default=None, min_length=1, max_length=50)

    @model_validator(mode="after")
    def authorization_confirmed_by_caller(self) -> "KnowledgeSearchRequest":
        if not self.authorization_confirmed:
            raise ValueError("Project authorization must be explicitly confirmed.")
        return self


class RetrievedKnowledge(CommonSchema):
    document_id: str
    content: str
    source_type: KnowledgeSourceType
    source_reference: str
    similarity_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeDocumentSummary(CommonSchema):
    document_id: str
    title: str
    source_type: KnowledgeSourceType
    source_reference: str
    project_id: UUID
    execution_id: UUID | None = None
    chunk_count: int
    created_at: datetime
    ingestion_status: str = "indexed"


class KnowledgeDocumentDetail(CommonSchema):
    summary: KnowledgeDocumentSummary
    content: str


class KnowledgeIngestResponse(CommonSchema):
    documents: list[KnowledgeDocumentSummary]
    duplicate_count: int = 0


class KnowledgeListResponse(CommonSchema):
    items: list[KnowledgeDocumentSummary]
    next_offset: int | None = None


class KnowledgeHealthResponse(CommonSchema):
    enabled: bool
    available: bool
    embedding_model: str
    collection_name: str
    error_category: str | None = None
