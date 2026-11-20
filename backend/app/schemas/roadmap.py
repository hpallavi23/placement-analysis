from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RoadmapTaskResponse(BaseModel):
    id: int
    user_id: int
    role: str
    skill_name: str
    current_level: int
    required_level: int
    recommendation: str
    priority: str
    is_completed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoadmapTaskCompleteResponse(BaseModel):
    message: str
    task: RoadmapTaskResponse
