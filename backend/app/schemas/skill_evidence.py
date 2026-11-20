from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EvidenceCreate(BaseModel):
    evidence_type: str = Field(min_length=2, max_length=50)
    title: str = Field(min_length=2, max_length=150)
    url: str = Field(min_length=4, max_length=500)
    description: Optional[str] = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class EvidenceReviewRequest(BaseModel):
    status: Literal["approved", "rejected"]
    reviewer_notes: Optional[str] = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class EvidenceResponse(BaseModel):
    id: int
    skill_id: int
    user_id: int
    evidence_type: str
    title: str
    url: str
    description: Optional[str] = None
    status: str
    reviewer_id: Optional[int] = None
    reviewer_notes: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
