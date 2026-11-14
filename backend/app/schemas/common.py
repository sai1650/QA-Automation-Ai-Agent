from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class CommonSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        ser_json_temporal="iso8601",
    )


class ApiResponse(CommonSchema, Generic[T]):
    data: T
    message: str | None = None


class PaginationParams(CommonSchema):
    page: int = Field(default=1, ge=1, description="One-based page number.")
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of items on a page.",
    )


class ErrorDetail(CommonSchema):
    code: str = Field(min_length=1, description="Stable machine-readable code.")
    message: str = Field(min_length=1, description="Safe user-facing message.")
    details: list[dict[str, object]] | None = None


class ErrorResponse(CommonSchema):
    error: ErrorDetail
