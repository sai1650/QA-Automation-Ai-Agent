from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import CommonSchema


class ExecutionStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionCreate(CommonSchema):
    requirements: str = Field(min_length=1, max_length=20000)
    options: dict[str, Any] | None = Field(default=None, max_length=100)
    authorized_target_confirmation: bool = Field(
        description="Confirms authorization to test the selected target."
    )

    @field_validator("authorized_target_confirmation")
    @classmethod
    def authorization_must_be_confirmed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Authorization must be confirmed.")
        return value

    @field_validator("requirements")
    @classmethod
    def requirements_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Requirements must not be blank.")
        return normalized


class ExecutionResponse(CommonSchema):
    id: UUID
    project_id: UUID
    status: ExecutionStatus
    requirements: str
    options: dict[str, Any]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None = None
    final_url: str | None = None
    inspection_result: dict[str, Any] | None = None


class ArtifactMetadata(CommonSchema):
    name: str = Field(min_length=1, max_length=120)
    media_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(ge=0)


class InspectionResponse(CommonSchema):
    execution_id: UUID
    status: ExecutionStatus
    duration_ms: int | None = None
    final_url: str | None = None
    result: dict[str, Any] | None = None


class ExecutionArtifactsResponse(CommonSchema):
    execution_id: UUID
    items: list[ArtifactMetadata]


class ExecutionListResponse(CommonSchema):
    items: list[ExecutionResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class ExecutionProgress(CommonSchema):
    execution_id: UUID
    current_stage: str = Field(min_length=1, max_length=120)
    completed_steps: int = Field(ge=0)
    total_steps: int = Field(ge=0)
    progress_percentage: float = Field(ge=0, le=100)
