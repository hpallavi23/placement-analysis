from datetime import datetime
from pydantic import BaseModel, ConfigDict


class StudentSummary(BaseModel):
    user_id: int
    email: str
    full_name: str | None = None
    college: str | None = None
    branch: str | None = None
    graduation_year: int | None = None
    cgpa: float | None = None

    model_config = ConfigDict(from_attributes=True)


class ReadinessSummary(BaseModel):
    has_assessment: bool
    overall_readiness_score: float | None = None
    aptitude_score: float | None = None
    technical_score: float | None = None
    communication_score: float | None = None
    problem_solving_score: float | None = None
    last_assessed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SkillSnippet(BaseModel):
    skill_name: str
    proficiency: int


class SkillsOverview(BaseModel):
    total_skills_logged: int
    top_skills: list[SkillSnippet]


class RoleReadinessItem(BaseModel):
    role: str
    readiness_percentage: float
    status: str


class RoadmapTaskSnippet(BaseModel):
    id: int
    skill_name: str
    current_level: int
    required_level: int
    priority: str
    recommendation: str


class RoadmapProgressSummary(BaseModel):
    has_active_roadmap: bool
    active_role: str | None = None
    enrolled_roles: list[str] = []
    total_tasks: int
    completed_tasks: int
    completion_percentage: float
    pending_high_priority_tasks: list[RoadmapTaskSnippet]


class DashboardResponse(BaseModel):
    student: StudentSummary
    readiness: ReadinessSummary
    skills_overview: SkillsOverview
    role_readiness: list[RoleReadinessItem]
    best_fit_role: str | None = None
    roadmap_progress: RoadmapProgressSummary
    recommended_next_action: str
