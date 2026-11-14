from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import Field

from app.schemas.common import CommonSchema


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"


class Approval(CommonSchema):
    id: UUID
    execution_id: UUID
    action_description: str = Field(min_length=1, max_length=2000)
    decision: ApprovalDecision
    reviewer_comment: str | None = Field(default=None, max_length=5000)
    created_at: datetime
    reviewed_at: datetime | None
