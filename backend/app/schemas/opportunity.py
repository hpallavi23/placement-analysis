from pydantic import BaseModel, ConfigDict, Field


class MissingSkillDetail(BaseModel):
    skill: str
    current_level: int
    required_level: int
    gap: int


class OpportunityMatchResult(BaseModel):
    id: int
    company_name: str
    role_title: str
    package_lpa: float
    min_cgpa: float
    location: str
    description: str | None = None
    required_skills: dict[str, int]
    cgpa_eligibility_status: str  # "Eligible" | "Not Eligible" | "Unknown (CGPA not provided)"
    is_eligible_cgpa: bool | None
    skill_match_percentage: float
    overall_fit_score: float = Field(
        description="Illustrative rule-based heuristic fit score (0-100), not a placement probability or ML prediction."
    )
    score_type: str = "rule_based_heuristic"
    status: str
    missing_skills: list[MissingSkillDetail]
    benchmark_disclaimer: str = (
        "Illustrative benchmark opportunity for readiness analysis; "
        "not verified live recruitment data."
    )

    model_config = ConfigDict(from_attributes=True)
