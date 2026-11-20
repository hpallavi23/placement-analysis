from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.skill import Skill
from app.models.skill_evidence import SkillEvidence
from app.models.user import User
from app.schemas.skill import SkillCreate, SkillResponse, EvidenceCounts
from app.schemas.skill_evidence import (
    EvidenceCreate,
    EvidenceReviewRequest,
    EvidenceResponse,
)
from app.api.v1.endpoints.auth import get_current_user, get_current_reviewer
from app.services.skill_gap import (
    ROLE_REQUIREMENTS,
    calculate_skill_gap,
)
from app.services.evidence_scoring import score_skill_evidence


router = APIRouter(prefix="/skills", tags=["Skill Gap Analysis"])


def _enrich_skill_response(skill: Skill) -> SkillResponse:
    """Enrich a Skill ORM model with evidence-aware scoring calculations."""
    score = score_skill_evidence(
        reported_proficiency=skill.proficiency,
        evidence_items=skill.evidence_submissions,
        has_skill=True,
    )
    return SkillResponse(
        id=skill.id,
        user_id=skill.user_id,
        skill_name=skill.skill_name,
        proficiency=skill.proficiency,
        evidence_level=score["evidence_level"],
        lambda_weight=score["lambda_weight"],
        adjusted_proficiency=score["adjusted_proficiency"],
        evidence_counts=EvidenceCounts(**score["evidence_counts"]),
    )


# ============================================================================
# Existing Skill CRUD Endpoints (Enriched with Evidence Scoring)
# ============================================================================

# Add or update a skill
@router.post("/", response_model=SkillResponse)
def add_skill(
    data: SkillCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    name = data.skill_name.strip()

    skill = db.query(Skill).filter(
        Skill.user_id == user.id,
        Skill.skill_name.ilike(name)
    ).first()

    if skill:
        skill.proficiency = data.proficiency
    else:
        skill = Skill(
            user_id=user.id,
            skill_name=name,
            proficiency=data.proficiency
        )
        db.add(skill)

    db.commit()
    db.refresh(skill)

    return _enrich_skill_response(skill)


# View all saved skills
@router.get("/", response_model=list[SkillResponse])
def get_skills(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    skills = db.query(Skill).filter(
        Skill.user_id == user.id
    ).all()
    return [_enrich_skill_response(s) for s in skills]


# View supported roles (Registered before variable paths)
@router.get("/roles")
def get_roles(
    user: User = Depends(get_current_user)
):
    return list(ROLE_REQUIREMENTS.keys())


# Calculate skill gap for a role
@router.get("/gap/{role}")
def get_skill_gap(
    role: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    user_skills = db.query(Skill).filter(
        Skill.user_id == user.id
    ).all()

    result = calculate_skill_gap(user_skills, role)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Role not supported"
        )

    return result


# ============================================================================
# Reviewer Endpoints (Fixed paths registered before variable skill_id paths)
# ============================================================================

# View pending evidence submissions across students
@router.get("/evidence/pending", response_model=list[EvidenceResponse])
def get_pending_evidence(
    db: Session = Depends(get_db),
    reviewer: User = Depends(get_current_reviewer)
):
    return db.query(SkillEvidence).filter(
        SkillEvidence.status == "pending"
    ).order_by(SkillEvidence.created_at.asc()).all()


# Review a pending evidence submission (Approve / Reject)
@router.post("/evidence/{evidence_id}/review", response_model=EvidenceResponse)
def review_skill_evidence(
    evidence_id: int,
    data: EvidenceReviewRequest,
    db: Session = Depends(get_db),
    reviewer: User = Depends(get_current_reviewer)
):
    evidence = db.query(SkillEvidence).filter(
        SkillEvidence.id == evidence_id
    ).first()

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence submission not found"
        )

    # Enforce Anti-Self-Review
    if evidence.user_id == reviewer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Self-review is strictly prohibited. You cannot review your own evidence submission."
        )

    # Only pending submissions may be reviewed
    if evidence.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Evidence has already been reviewed (current status: '{evidence.status}')."
        )

    evidence.status = data.status
    evidence.reviewer_id = reviewer.id
    evidence.reviewer_notes = data.reviewer_notes.strip() if data.reviewer_notes else None
    evidence.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(evidence)

    return evidence


# Delete an evidence submission (Student owner, pending only)
@router.delete("/evidence/{evidence_id}", status_code=status.HTTP_200_OK)
def delete_skill_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    evidence = db.query(SkillEvidence).filter(
        SkillEvidence.id == evidence_id,
        SkillEvidence.user_id == user.id
    ).first()

    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence submission not found"
        )

    if evidence.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete evidence with status '{evidence.status}'. Only pending evidence may be deleted."
        )

    db.delete(evidence)
    db.commit()

    return {"message": "Evidence deleted successfully", "id": evidence_id}


# ============================================================================
# Student Evidence Submission & Retrieval Endpoints
# ============================================================================

# Submit evidence for an existing owned skill
@router.post("/{skill_id}/evidence", response_model=EvidenceResponse, status_code=status.HTTP_201_CREATED)
def submit_skill_evidence(
    skill_id: int,
    data: EvidenceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    skill = db.query(Skill).filter(
        Skill.id == skill_id,
        Skill.user_id == user.id
    ).first()

    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found in your profile"
        )

    evidence = SkillEvidence(
        skill_id=skill.id,
        user_id=user.id,
        evidence_type=data.evidence_type.strip(),
        title=data.title.strip(),
        url=data.url.strip(),
        description=data.description.strip() if data.description else None,
        status="pending",
        reviewer_id=None,
        reviewer_notes=None,
        reviewed_at=None,
    )

    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    return evidence


# View evidence submissions for a skill (Owner or Authorized Reviewer)
@router.get("/{skill_id}/evidence", response_model=list[EvidenceResponse])
def get_skill_evidence(
    skill_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    skill = db.query(Skill).filter(Skill.id == skill_id).first()

    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found"
        )

    is_owner = (skill.user_id == user.id)
    user_email = (user.email or "").strip().lower()
    is_reviewer = bool(
        settings.allowed_reviewer_emails and
        user_email in settings.allowed_reviewer_emails
    )

    if not is_owner and not is_reviewer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access evidence for this skill"
        )

    return db.query(SkillEvidence).filter(
        SkillEvidence.skill_id == skill.id
    ).order_by(SkillEvidence.created_at.desc()).all()


# Delete an existing skill (Preserved original endpoint)
@router.delete("/{skill_id}", status_code=status.HTTP_200_OK)
def delete_skill(
    skill_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    skill = db.query(Skill).filter(
        Skill.id == skill_id,
        Skill.user_id == user.id
    ).first()

    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found"
        )

    db.delete(skill)
    db.commit()

    return {"message": "Skill deleted successfully", "id": skill_id}
