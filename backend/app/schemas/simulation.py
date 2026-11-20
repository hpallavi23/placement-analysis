from pydantic import BaseModel, Field, ConfigDict


class WhatIfRequest(BaseModel):
    target_role: str | None = None
    simulated_cgpa: float | None = Field(default=None, ge=0.0, le=10.0)
    simulated_skills: dict[str, int] | None = None  # e.g. {"Python": 4, "SQL": 4, "DSA": 4}
    simulated_aptitude: float | None = Field(default=None, ge=0.0, le=100.0)
    simulated_technical: float | None = Field(default=None, ge=0.0, le=100.0)
    simulated_communication: float | None = Field(default=None, ge=0.0, le=100.0)
    simulated_problem_solving: float | None = Field(default=None, ge=0.0, le=100.0)


class MetricComparison(BaseModel):
    current: float | None = None
    simulated: float
    delta: float | None = None


class RoleComparisonItem(BaseModel):
    role: str
    current_readiness: float
    simulated_readiness: float
    delta: float
    status_before: str
    status_after: str


class OpportunitiesComparison(BaseModel):
    current_eligible_count: int
    simulated_eligible_count: int
    newly_unlocked_companies: list[str]
    average_fit_score_before: float
    average_fit_score_after: float


class WhatIfResponse(BaseModel):
    readiness_score: MetricComparison | None = None
    target_role: str | None = None
    target_role_readiness: MetricComparison | None = None
    all_roles_readiness: list[RoleComparisonItem]
    opportunities_impact: OpportunitiesComparison
    insights: list[str]
    simulation_disclaimer: str = (
        "Illustrative rule-based simulation heuristic for planning; "
        "does not guarantee hiring outcomes."
    )

    model_config = ConfigDict(from_attributes=True)
