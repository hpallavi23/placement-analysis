from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class EvidenceCounts(BaseModel):
    total: int = 0
    approved: int = 0
    pending: int = 0
    rejected: int = 0


class SkillCreate(BaseModel):
    skill_name: str = Field(min_length=2, max_length=100)
    proficiency: int = Field(ge=0, le=5)


class SkillResponse(SkillCreate):
    id: int
    user_id: int
    evidence_level: Optional[str] = "E1"
    lambda_weight: Optional[float] = 0.5
    adjusted_proficiency: Optional[float] = None
    evidence_counts: Optional[EvidenceCounts] = None

    model_config = ConfigDict(from_attributes=True)