from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.student_profile import StudentProfile
from app.models.user import User
from app.schemas.student_profile import (
    StudentProfileCreate,
    StudentProfileUpdate,
    StudentProfileResponse
)
from app.api.v1.endpoints.auth import get_current_user


router = APIRouter(prefix="/profile", tags=["Student Profile"])


@router.post("/", response_model=StudentProfileResponse, status_code=201)
def create_profile(
    data: StudentProfileCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    existing = db.query(StudentProfile).filter(
        StudentProfile.user_id == user.id
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail="Profile already exists")

    profile = StudentProfile(user_id=user.id, **data.model_dump())

    db.add(profile)
    db.commit()
    db.refresh(profile)

    return profile


@router.get("/", response_model=StudentProfileResponse)
def get_profile(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == user.id
    ).first()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return profile


@router.put("/", response_model=StudentProfileResponse)
def update_profile(
    data: StudentProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    profile = db.query(StudentProfile).filter(
        StudentProfile.user_id == user.id
    ).first()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)

    db.commit()
    db.refresh(profile)

    return profile