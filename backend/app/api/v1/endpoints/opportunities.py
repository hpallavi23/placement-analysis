from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.student_profile import StudentProfile
from app.models.skill import Skill
from app.models.user import User
from app.schemas.opportunity import OpportunityMatchResult
from app.api.v1.endpoints.auth import get_current_user
from app.services.opportunity import (
    get_all_opportunity_matches,
    get_opportunity_match_by_id
)


router = APIRouter(prefix="/opportunities", tags=["Placement Opportunities"])


@router.get("/", response_model=list[OpportunityMatchResult])
def get_opportunities(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == user.id
    ).first()
    user_cgpa = profile.cgpa if profile else None

    user_skills = db.query(Skill).filter(
        Skill.user_id == user.id
    ).all()

    return get_all_opportunity_matches(user_cgpa, user_skills)


@router.get("/{opportunity_id}", response_model=OpportunityMatchResult)
def get_opportunity_detail(
    opportunity_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == user.id
    ).first()
    user_cgpa = profile.cgpa if profile else None

    user_skills = db.query(Skill).filter(
        Skill.user_id == user.id
    ).all()

    result = get_opportunity_match_by_id(opportunity_id, user_cgpa, user_skills)
    if not result:
        raise HTTPException(
            status_code=404,
            detail="Placement opportunity not found"
        )

    return result
