from enum import Enum
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import CommonSchema

__test__ = False


class TestCasePriority(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class TestStep(CommonSchema):
    order: int = Field(ge=1)
    action: str = Field(min_length=1, max_length=1000)
    expected_outcome: str | None = Field(default=None, max_length=1000)

    @field_validator("action")
    @classmethod
    def action_must_not_be_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Step action must not be blank.")
        return normalized


class TestCase(CommonSchema):
    id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    preconditions: list[str] = Field(default_factory=list, max_length=50)
    steps: list[TestStep] = Field(min_length=1, max_length=100)
    expected_result: str = Field(min_length=1, max_length=2000)
    priority: TestCasePriority
    category: str = Field(min_length=1, max_length=100)
