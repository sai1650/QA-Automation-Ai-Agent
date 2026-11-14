from datetime import datetime
from uuid import UUID

from pydantic import Field, HttpUrl, field_validator, model_validator

from app.schemas.common import CommonSchema


class ProjectCreate(CommonSchema):
    name: str = Field(min_length=1, max_length=120, description="Project name.")
    base_url: HttpUrl = Field(description="HTTP or HTTPS URL for the target.")
    description: str | None = Field(default=None, max_length=5000)
    authorization_confirmed: bool = Field(
        description="Confirms authorization to assess the target."
    )

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Project name must not be blank.")
        return normalized

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("authorization_confirmed")
    @classmethod
    def authorization_must_be_confirmed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Authorization must be confirmed.")
        return value


class ProjectUpdate(CommonSchema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    base_url: HttpUrl | None = None
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def optional_name_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Project name must not be blank.")
        return normalized

    @field_validator("description")
    @classmethod
    def optional_description_must_not_be_blank(
        cls, value: str | None
    ) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "ProjectUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one project field must be provided.")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Project name cannot be null.")
        if "base_url" in self.model_fields_set and self.base_url is None:
            raise ValueError("Project URL cannot be null.")
        return self


class ProjectResponse(CommonSchema):
    id: UUID
    name: str
    base_url: HttpUrl
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(CommonSchema):
    items: list[ProjectResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class ProjectArchiveResponse(CommonSchema):
    id: UUID
    is_active: bool
    message: str
