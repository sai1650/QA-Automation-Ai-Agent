from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import CommonSchema


class Report(CommonSchema):
    id: UUID
    execution_id: UUID
    total_tests: int = Field(ge=0)
    passed_tests: int = Field(ge=0)
    failed_tests: int = Field(ge=0)
    skipped_tests: int = Field(ge=0)
    findings_count: int = Field(ge=0)
    summary: str = Field(min_length=1, max_length=10000)
    generated_at: datetime
    artifact_reference: str | None = Field(default=None, max_length=2048)
