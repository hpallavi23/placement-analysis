from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssessmentCreate(BaseModel):
    aptitude_score: float = Field(ge=0, le=100)
    technical_score: float = Field(ge=0, le=100)
    communication_score: float = Field(ge=0, le=100)
    problem_solving_score: float = Field(ge=0, le=100)


class AssessmentResponse(AssessmentCreate):
    id: int
    user_id: int
    readiness_score: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)