from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.assessment import Assessment
from app.models.user import User
from app.schemas.assessment import AssessmentCreate, AssessmentResponse
from app.api.v1.endpoints.auth import get_current_user
from app.services.readiness import calculate_readiness_score


router = APIRouter(prefix="/assessments", tags=["Assessments"])


# Submit a new assessment
@router.post("/", response_model=AssessmentResponse, status_code=201)
def create_assessment(
    data: AssessmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    readiness = calculate_readiness_score(
        data.aptitude_score,
        data.technical_score,
        data.communication_score,
        data.problem_solving_score
    )

    assessment = Assessment(
        user_id=user.id,
        **data.model_dump(),
        readiness_score=readiness
    )

    db.add(assessment)
    db.commit()
    db.refresh(assessment)

    return assessment


# Get the latest assessment
@router.get("/latest", response_model=AssessmentResponse)
def get_latest_assessment(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    assessment = db.query(Assessment).filter(
        Assessment.user_id == user.id
    ).order_by(Assessment.created_at.desc()).first()

    if not assessment:
        raise HTTPException(status_code=404, detail="No assessment found")

    return assessment


# Get assessment history
@router.get("/history", response_model=list[AssessmentResponse])
def get_assessment_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return db.query(Assessment).filter(
        Assessment.user_id == user.id
    ).order_by(Assessment.created_at.desc()).all()