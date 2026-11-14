from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import Field

from app.schemas.common import CommonSchema


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FindingStatus(str, Enum):
    OPEN = "OPEN"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    RESOLVED = "RESOLVED"


class Finding(CommonSchema):
    id: UUID
    execution_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    severity: Severity
    status: FindingStatus
    reproduction_steps: list[str] = Field(min_length=1, max_length=100)
    expected_result: str = Field(min_length=1, max_length=2000)
    actual_result: str = Field(min_length=1, max_length=2000)
    evidence_references: list[str] = Field(default_factory=list, max_length=100)
    created_at: datetime
