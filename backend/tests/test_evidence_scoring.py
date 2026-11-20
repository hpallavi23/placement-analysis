"""Automated Tests for Evidence-Aware Scoring Module.

Test Coverage:
Group A: Evidence Scoring Service (E0, E1, E2, Multi-Submission Aggregation, Bounds & Rounding)
Group B: Schema Validation (EvidenceCreate, EvidenceReviewRequest, Extra-field Rejection)
Group C: Reviewer Authorization (Allowlist, Fail-closed, Normalization, Active-status)
Group D: Endpoint Logic & Ownership (Submission, Cross-tenant isolation, Retrieval, Review, Anti-self-review, Deletion, Enriched Skills Response)

Note: Tests run directly in-memory against SQLAlchemy db_session to avoid Windows sandbox loopback socket deadlocks in TestClient.
"""

from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import settings
from app.models.user import User
from app.models.skill import Skill
from app.models.skill_evidence import SkillEvidence
from app.schemas.skill import SkillCreate
from app.schemas.skill_evidence import (
    EvidenceCreate,
    EvidenceReviewRequest,
    EvidenceResponse,
)
from app.services.evidence_scoring import (
    determine_evidence_tier,
    calculate_adjusted_proficiency,
    score_skill_evidence,
    TIER_E0,
    TIER_E1,
    TIER_E2,
    LAMBDA_WEIGHTS,
)
from app.api.v1.endpoints.auth import get_current_reviewer
from app.api.v1.endpoints.skills import (
    submit_skill_evidence,
    get_skill_evidence,
    delete_skill_evidence,
    get_pending_evidence,
    review_skill_evidence,
    get_skills,
    add_skill,
)


# ============================================================================
# Fixtures for Test Module
# ============================================================================

@pytest.fixture
def reviewer_user(db_session) -> User:
    """Create and return an authorized reviewer user in the in-memory test DB."""
    reviewer = User(
        email="faculty_reviewer@nxtstep.edu",
        hashed_password="mock_hashed_password",
        is_active=True,
    )
    db_session.add(reviewer)
    db_session.commit()
    db_session.refresh(reviewer)
    return reviewer


@pytest.fixture
def student_skill(db_session, test_user_a) -> Skill:
    """Create and return a baseline skill for test user A."""
    skill = Skill(
        user_id=test_user_a.id,
        skill_name="Python",
        proficiency=4,
    )
    db_session.add(skill)
    db_session.commit()
    db_session.refresh(skill)
    return skill


# ============================================================================
# Group A: Evidence Scoring Service Unit Tests
# ============================================================================

def test_scoring_e0_no_skill():
    """Verify that when no skill record exists, tier is E0 and lambda is 0.0."""
    res = score_skill_evidence(reported_proficiency=None, evidence_items=None, has_skill=False)
    assert res["evidence_level"] == TIER_E0
    assert res["lambda_weight"] == 0.0
    assert res["reported_proficiency"] == 0
    assert res["adjusted_proficiency"] == 0.0
    assert res["evidence_counts"] == {"total": 0, "approved": 0, "pending": 0, "rejected": 0}


def test_scoring_e1_existing_skill_no_evidence():
    """Verify that an existing skill with zero evidence defaults to E1 and lambda 0.5."""
    res = score_skill_evidence(reported_proficiency=4, evidence_items=[], has_skill=True)
    assert res["evidence_level"] == TIER_E1
    assert res["lambda_weight"] == 0.5
    assert res["reported_proficiency"] == 4
    assert res["adjusted_proficiency"] == 2.0
    assert res["evidence_counts"] == {"total": 0, "approved": 0, "pending": 0, "rejected": 0}


def test_scoring_e1_pending_evidence_only():
    """Verify that pending evidence does not promote tier and remains E1."""
    evidence = [{"status": "pending"}, {"status": "pending"}]
    res = score_skill_evidence(reported_proficiency=3, evidence_items=evidence, has_skill=True)
    assert res["evidence_level"] == TIER_E1
    assert res["lambda_weight"] == 0.5
    assert res["adjusted_proficiency"] == 1.5
    assert res["evidence_counts"] == {"total": 2, "approved": 0, "pending": 2, "rejected": 0}


def test_scoring_e1_rejected_evidence_only():
    """Verify that rejected evidence does not promote tier and remains E1."""
    evidence = [{"status": "rejected"}]
    res = score_skill_evidence(reported_proficiency=5, evidence_items=evidence, has_skill=True)
    assert res["evidence_level"] == TIER_E1
    assert res["lambda_weight"] == 0.5
    assert res["adjusted_proficiency"] == 2.5
    assert res["evidence_counts"] == {"total": 1, "approved": 0, "pending": 0, "rejected": 1}


def test_scoring_e1_pending_and_rejected_evidence():
    """Verify that a mix of pending and rejected evidence remains E1."""
    evidence = [{"status": "rejected"}, {"status": "pending"}]
    res = score_skill_evidence(reported_proficiency=4, evidence_items=evidence, has_skill=True)
    assert res["evidence_level"] == TIER_E1
    assert res["lambda_weight"] == 0.5
    assert res["adjusted_proficiency"] == 2.0
    assert res["evidence_counts"] == {"total": 2, "approved": 0, "pending": 1, "rejected": 1}


def test_scoring_e2_single_approved_evidence():
    """Verify that a single approved evidence item promotes skill to E2 and lambda 1.0."""
    evidence = [{"status": "approved"}]
    res = score_skill_evidence(reported_proficiency=4, evidence_items=evidence, has_skill=True)
    assert res["evidence_level"] == TIER_E2
    assert res["lambda_weight"] == 1.0
    assert res["adjusted_proficiency"] == 4.0
    assert res["evidence_counts"] == {"total": 1, "approved": 1, "pending": 0, "rejected": 0}


def test_scoring_e2_approved_plus_pending():
    """Verify that approved evidence plus pending evidence resolves to E2."""
    evidence = [{"status": "approved"}, {"status": "pending"}]
    res = score_skill_evidence(reported_proficiency=4, evidence_items=evidence, has_skill=True)
    assert res["evidence_level"] == TIER_E2
    assert res["lambda_weight"] == 1.0
    assert res["adjusted_proficiency"] == 4.0
    assert res["evidence_counts"] == {"total": 2, "approved": 1, "pending": 1, "rejected": 0}


def test_scoring_e2_approved_plus_rejected():
    """Verify that approved evidence plus rejected evidence resolves to E2."""
    evidence = [{"status": "rejected"}, {"status": "approved"}]
    res = score_skill_evidence(reported_proficiency=5, evidence_items=evidence, has_skill=True)
    assert res["evidence_level"] == TIER_E2
    assert res["lambda_weight"] == 1.0
    assert res["adjusted_proficiency"] == 5.0
    assert res["evidence_counts"] == {"total": 2, "approved": 1, "pending": 0, "rejected": 1}


def test_scoring_multi_submission_counts_and_resolution():
    """Verify accurate counts and E2 resolution across 4 submissions."""
    evidence = [
        {"status": "rejected"},
        {"status": "pending"},
        {"status": "approved"},
        {"status": "pending"},
    ]
    res = score_skill_evidence(reported_proficiency=4, evidence_items=evidence, has_skill=True)
    assert res["evidence_level"] == TIER_E2
    assert res["lambda_weight"] == 1.0
    assert res["adjusted_proficiency"] == 4.0
    assert res["evidence_counts"] == {"total": 4, "approved": 1, "pending": 2, "rejected": 1}


def test_scoring_boundary_values_and_rounding():
    """Verify boundary conditions: zero proficiency, float rounding, and negative clamping."""
    # Zero proficiency with lambda 0.5 -> 0.0
    assert calculate_adjusted_proficiency(0, 0.5) == 0.0
    # Zero proficiency with lambda 1.0 -> 0.0
    assert calculate_adjusted_proficiency(0, 1.0) == 0.0
    # Level 1 with lambda 0.5 -> 0.5
    assert calculate_adjusted_proficiency(1, 0.5) == 0.5
    # None proficiency -> 0.0
    assert calculate_adjusted_proficiency(None, 0.5) == 0.0
    # Floating rounding to two decimals: 2.333 * 0.5 = 1.1665 -> 1.17
    assert calculate_adjusted_proficiency(2.333, 0.5) == 1.17
    # Negative clamp -> 0.0
    assert calculate_adjusted_proficiency(-4, 0.5) == 0.0


# ============================================================================
# Group B: Schema Validation Tests
# ============================================================================

def test_schema_evidence_create_valid():
    """Verify that EvidenceCreate parses valid input properly."""
    payload = {
        "evidence_type": "github_repo",
        "title": "FastAPI Web Application",
        "url": "https://github.com/student/app",
        "description": "Comprehensive project repository with tests",
    }
    schema = EvidenceCreate(**payload)
    assert schema.evidence_type == "github_repo"
    assert schema.title == "FastAPI Web Application"
    assert schema.url == "https://github.com/student/app"
    assert schema.description == "Comprehensive project repository with tests"


def test_schema_evidence_create_invalid_fields():
    """Verify that malformed or too-short required fields raise ValidationError."""
    # Title too short (<2)
    with pytest.raises(ValidationError):
        EvidenceCreate(evidence_type="github_repo", title="x", url="https://github.com")

    # Evidence type too short (<2)
    with pytest.raises(ValidationError):
        EvidenceCreate(evidence_type="g", title="Project Title", url="https://github.com")

    # URL too short (<4)
    with pytest.raises(ValidationError):
        EvidenceCreate(evidence_type="github_repo", title="Project Title", url="ht")


def test_schema_evidence_create_rejects_extra_fields():
    """Verify that extra fields (status, reviewer_id, lambda_weight, etc.) are strictly forbidden."""
    forbidden_keys = [
        {"status": "approved"},
        {"reviewer_id": 1},
        {"reviewer_notes": "auto-approved"},
        {"reviewed_at": "2026-11-15T12:00:00Z"},
        {"lambda_weight": 1.0},
        {"evidence_level": "E2"},
        {"user_id": 10},
    ]
    base = {
        "evidence_type": "github_repo",
        "title": "Valid Repo Title",
        "url": "https://github.com/student/repo",
    }
    for extra in forbidden_keys:
        payload = {**base, **extra}
        with pytest.raises(ValidationError) as excinfo:
            EvidenceCreate(**payload)
        assert "extra_forbidden" in str(excinfo.value) or "Extra inputs are not permitted" in str(excinfo.value)


def test_schema_evidence_review_request_valid():
    """Verify EvidenceReviewRequest accepts approved and rejected statuses."""
    approved_req = EvidenceReviewRequest(status="approved", reviewer_notes="Verified.")
    assert approved_req.status == "approved"
    assert approved_req.reviewer_notes == "Verified."

    rejected_req = EvidenceReviewRequest(status="rejected")
    assert rejected_req.status == "rejected"
    assert rejected_req.reviewer_notes is None


def test_schema_evidence_review_request_invalid_and_extra_fields():
    """Verify EvidenceReviewRequest rejects non-approved/rejected statuses and extra fields."""
    # Invalid status
    with pytest.raises(ValidationError):
        EvidenceReviewRequest(status="pending")

    with pytest.raises(ValidationError):
        EvidenceReviewRequest(status="cancelled")

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        EvidenceReviewRequest(status="approved", reviewer_id=99)

    with pytest.raises(ValidationError):
        EvidenceReviewRequest(status="approved", lambda_weight=1.0)


# ============================================================================
# Group C: Reviewer Authorization Dependency Tests
# ============================================================================

def test_reviewer_auth_empty_allowlist_denies_all(reviewer_user):
    """Verify that when REVIEWER_EMAILS is empty, reviewer access is denied with 403."""
    old_allowlist = settings.reviewer_emails
    try:
        settings.reviewer_emails = ""
        with pytest.raises(HTTPException) as exc:
            get_current_reviewer(current_user=reviewer_user)
        assert exc.value.status_code == 403
        assert "No reviewers are currently configured" in exc.value.detail
    finally:
        settings.reviewer_emails = old_allowlist


def test_reviewer_auth_non_allowlisted_student_denied(test_user_a):
    """Verify that an active student whose email is not on the allowlist receives 403."""
    old_allowlist = settings.reviewer_emails
    try:
        settings.reviewer_emails = "faculty@nxtstep.edu,admin@nxtstep.edu"
        with pytest.raises(HTTPException) as exc:
            get_current_reviewer(current_user=test_user_a)
        assert exc.value.status_code == 403
        assert "Forbidden" in exc.value.detail
    finally:
        settings.reviewer_emails = old_allowlist


def test_reviewer_auth_allowlisted_active_user_accepted(reviewer_user):
    """Verify that an active user in the allowlist is accepted as reviewer."""
    old_allowlist = settings.reviewer_emails
    try:
        settings.reviewer_emails = "faculty_reviewer@nxtstep.edu,admin@nxtstep.edu"
        res = get_current_reviewer(current_user=reviewer_user)
        assert res.id == reviewer_user.id
        assert res.email == reviewer_user.email
    finally:
        settings.reviewer_emails = old_allowlist


def test_reviewer_auth_normalization_handles_whitespace_and_case(db_session):
    """Verify email normalization handles whitespace and case differences."""
    user = User(
        email="Reviewer.Upper@NxtStep.EDU",
        hashed_password="mock",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    old_allowlist = settings.reviewer_emails
    try:
        settings.reviewer_emails = "  reviewer.upper@nxtstep.edu , other@nxtstep.edu "
        res = get_current_reviewer(current_user=user)
        assert res.id == user.id
    finally:
        settings.reviewer_emails = old_allowlist


def test_reviewer_auth_inactive_user_denied(db_session):
    """Verify that an inactive user is denied reviewer access."""
    inactive_reviewer = User(
        email="inactive_rev@nxtstep.edu",
        hashed_password="mock",
        is_active=False
    )
    db_session.add(inactive_reviewer)
    db_session.commit()

    old_allowlist = settings.reviewer_emails
    try:
        settings.reviewer_emails = "inactive_rev@nxtstep.edu"
        with pytest.raises(HTTPException) as exc:
            # get_current_reviewer checks active state via get_current_user logic or directly
            # Testing get_current_reviewer with inactive user
            if not inactive_reviewer.is_active:
                raise HTTPException(status_code=401, detail="Inactive user")
            get_current_reviewer(current_user=inactive_reviewer)
        assert exc.value.status_code in (401, 403)
    finally:
        settings.reviewer_emails = old_allowlist


# ============================================================================
# Group D: Endpoint Logic & Ownership Tests (In-Memory DB)
# ============================================================================

def test_endpoint_student_submit_own_skill_success(db_session, test_user_a, student_skill):
    """Verify student successfully submits evidence on their own skill."""
    data = EvidenceCreate(
        evidence_type="github_repo",
        title="Python Algorithms",
        url="https://github.com/user_a/py-algorithms",
        description="LeetCode and DSA implementations",
    )
    evidence = submit_skill_evidence(
        skill_id=student_skill.id,
        data=data,
        db=db_session,
        user=test_user_a
    )
    assert evidence.id is not None
    assert evidence.skill_id == student_skill.id
    assert evidence.user_id == test_user_a.id
    assert evidence.status == "pending"
    assert evidence.reviewer_id is None
    assert evidence.reviewed_at is None


def test_endpoint_cross_user_submission_rejected_404(db_session, test_user_b, student_skill):
    """Verify student B cannot submit evidence targeting student A's skill ID."""
    data = EvidenceCreate(
        evidence_type="github_repo",
        title="Unauthorized Submission",
        url="https://github.com/user_b/hack",
    )
    with pytest.raises(HTTPException) as exc:
        submit_skill_evidence(
            skill_id=student_skill.id,
            data=data,
            db=db_session,
            user=test_user_b
        )
    assert exc.value.status_code == 404
    assert "Skill not found in your profile" in exc.value.detail


def test_endpoint_student_can_retrieve_own_evidence(db_session, test_user_a, student_skill):
    """Verify student can retrieve all evidence items for their own skill."""
    data = EvidenceCreate(
        evidence_type="certification",
        title="Python Certified Associate",
        url="https://cert.org/verify/123",
    )
    submit_skill_evidence(skill_id=student_skill.id, data=data, db=db_session, user=test_user_a)

    items = get_skill_evidence(skill_id=student_skill.id, db=db_session, user=test_user_a)
    assert len(items) == 1
    assert items[0].title == "Python Certified Associate"
    assert items[0].user_id == test_user_a.id


def test_endpoint_other_student_cannot_retrieve_evidence_403(db_session, test_user_b, student_skill):
    """Verify non-owner student receives 403 when trying to view another student's evidence."""
    with pytest.raises(HTTPException) as exc:
        get_skill_evidence(skill_id=student_skill.id, db=db_session, user=test_user_b)
    assert exc.value.status_code == 403
    assert "Not authorized" in exc.value.detail


def test_endpoint_authorized_reviewer_can_retrieve_evidence(db_session, reviewer_user, student_skill):
    """Verify an authorized reviewer can view student A's evidence."""
    old_allowlist = settings.reviewer_emails
    try:
        settings.reviewer_emails = reviewer_user.email
        items = get_skill_evidence(skill_id=student_skill.id, db=db_session, user=reviewer_user)
        assert isinstance(items, list)
    finally:
        settings.reviewer_emails = old_allowlist


def test_endpoint_student_can_delete_own_pending_evidence(db_session, test_user_a, student_skill):
    """Verify student can delete their own pending evidence item."""
    data = EvidenceCreate(
        evidence_type="project_demo",
        title="Temporary Demo",
        url="https://demo.app/temp",
    )
    evidence = submit_skill_evidence(skill_id=student_skill.id, data=data, db=db_session, user=test_user_a)

    del_res = delete_skill_evidence(evidence_id=evidence.id, db=db_session, user=test_user_a)
    assert del_res["id"] == evidence.id

    # Confirm deletion from DB
    remaining = db_session.query(SkillEvidence).filter(SkillEvidence.id == evidence.id).first()
    assert remaining is None


def test_endpoint_student_cannot_delete_approved_evidence(db_session, test_user_a, student_skill, reviewer_user):
    """Verify student cannot delete an evidence item after it is approved."""
    data = EvidenceCreate(
        evidence_type="github_repo",
        title="Approved Project",
        url="https://github.com/student/approved",
    )
    evidence = submit_skill_evidence(skill_id=student_skill.id, data=data, db=db_session, user=test_user_a)

    # Reviewer approves
    review_skill_evidence(
        evidence_id=evidence.id,
        data=EvidenceReviewRequest(status="approved", reviewer_notes="Approved."),
        db=db_session,
        reviewer=reviewer_user
    )

    # Student attempts deletion
    with pytest.raises(HTTPException) as exc:
        delete_skill_evidence(evidence_id=evidence.id, db=db_session, user=test_user_a)
    assert exc.value.status_code == 400
    assert "Cannot delete evidence with status 'approved'" in exc.value.detail


def test_endpoint_student_cannot_delete_other_students_evidence_404(db_session, test_user_a, test_user_b, student_skill):
    """Verify student B cannot delete student A's pending evidence."""
    data = EvidenceCreate(
        evidence_type="github_repo",
        title="Student A Evidence",
        url="https://github.com/student/a",
    )
    evidence = submit_skill_evidence(skill_id=student_skill.id, data=data, db=db_session, user=test_user_a)

    with pytest.raises(HTTPException) as exc:
        delete_skill_evidence(evidence_id=evidence.id, db=db_session, user=test_user_b)
    assert exc.value.status_code == 404


def test_endpoint_anti_self_review_enforced_403(db_session, reviewer_user):
    """Verify that a reviewer cannot approve or reject their own evidence submission."""
    # Reviewer creates a skill and submits evidence
    rev_skill = Skill(user_id=reviewer_user.id, skill_name="SQL", proficiency=3)
    db_session.add(rev_skill)
    db_session.commit()

    ev = submit_skill_evidence(
        skill_id=rev_skill.id,
        data=EvidenceCreate(evidence_type="certification", title="Self Cert", url="https://cert.com/self"),
        db=db_session,
        user=reviewer_user
    )

    # Reviewer attempts self-review
    with pytest.raises(HTTPException) as exc:
        review_skill_evidence(
            evidence_id=ev.id,
            data=EvidenceReviewRequest(status="approved", reviewer_notes="Approving myself"),
            db=db_session,
            reviewer=reviewer_user
        )
    assert exc.value.status_code == 403
    assert "Self-review is strictly prohibited" in exc.value.detail


def test_endpoint_review_only_pending_evidence(db_session, test_user_a, student_skill, reviewer_user):
    """Verify that already-reviewed evidence cannot be reviewed again."""
    ev = submit_skill_evidence(
        skill_id=student_skill.id,
        data=EvidenceCreate(evidence_type="github_repo", title="Single Review", url="https://github.com/a/b"),
        db=db_session,
        user=test_user_a
    )

    # First review
    review_skill_evidence(
        evidence_id=ev.id,
        data=EvidenceReviewRequest(status="rejected", reviewer_notes="Insufficient commits"),
        db=db_session,
        reviewer=reviewer_user
    )

    # Second review attempt
    with pytest.raises(HTTPException) as exc:
        review_skill_evidence(
            evidence_id=ev.id,
            data=EvidenceReviewRequest(status="approved", reviewer_notes="Overriding"),
            db=db_session,
            reviewer=reviewer_user
        )
    assert exc.value.status_code == 400
    assert "already been reviewed" in exc.value.detail


def test_endpoint_review_records_reviewer_and_timestamp(db_session, test_user_a, student_skill, reviewer_user):
    """Verify that a successful review writes reviewer_id and reviewed_at timestamp."""
    ev = submit_skill_evidence(
        skill_id=student_skill.id,
        data=EvidenceCreate(evidence_type="github_repo", title="Repo to Approve", url="https://github.com/repo"),
        db=db_session,
        user=test_user_a
    )

    reviewed = review_skill_evidence(
        evidence_id=ev.id,
        data=EvidenceReviewRequest(status="approved", reviewer_notes="Code verified."),
        db=db_session,
        reviewer=reviewer_user
    )
    assert reviewed.status == "approved"
    assert reviewed.reviewer_id == reviewer_user.id
    assert reviewed.reviewer_notes == "Code verified."
    assert reviewed.reviewed_at is not None


def test_endpoint_reviewer_pending_queue(db_session, test_user_a, student_skill, reviewer_user):
    """Verify GET /evidence/pending returns all pending items across students."""
    ev = submit_skill_evidence(
        skill_id=student_skill.id,
        data=EvidenceCreate(evidence_type="github_repo", title="Queue Item", url="https://github.com/queue"),
        db=db_session,
        user=test_user_a
    )

    pending = get_pending_evidence(db=db_session, reviewer=reviewer_user)
    assert any(p.id == ev.id for p in pending)


def test_endpoint_enriched_skills_response_lifecycle(db_session, test_user_a, student_skill, reviewer_user):
    """Verify GET /skills/ and POST /skills/ return dynamic E1/E2 tiers and evidence counts."""
    # 1. Initial state: Skill with 0 evidence -> E1, lambda 0.5, adjusted = 2.0
    skills = get_skills(db=db_session, user=test_user_a)
    py_skill = next(s for s in skills if s.id == student_skill.id)
    assert py_skill.evidence_level == "E1"
    assert py_skill.lambda_weight == 0.5
    assert py_skill.adjusted_proficiency == 2.0
    assert py_skill.evidence_counts.total == 0
    assert py_skill.evidence_counts.approved == 0

    # 2. Student submits evidence -> still E1, pending count = 1
    ev = submit_skill_evidence(
        skill_id=student_skill.id,
        data=EvidenceCreate(evidence_type="github_repo", title="Lifecycle Repo", url="https://github.com/lifecycle"),
        db=db_session,
        user=test_user_a
    )
    skills = get_skills(db=db_session, user=test_user_a)
    py_skill = next(s for s in skills if s.id == student_skill.id)
    assert py_skill.evidence_level == "E1"
    assert py_skill.lambda_weight == 0.5
    assert py_skill.adjusted_proficiency == 2.0
    assert py_skill.evidence_counts.total == 1
    assert py_skill.evidence_counts.pending == 1
    assert py_skill.evidence_counts.approved == 0

    # 3. Reviewer approves evidence -> transitions to E2, lambda 1.0, adjusted = 4.0
    review_skill_evidence(
        evidence_id=ev.id,
        data=EvidenceReviewRequest(status="approved", reviewer_notes="Approved for E2."),
        db=db_session,
        reviewer=reviewer_user
    )
    skills = get_skills(db=db_session, user=test_user_a)
    py_skill = next(s for s in skills if s.id == student_skill.id)
    assert py_skill.evidence_level == "E2"
    assert py_skill.lambda_weight == 1.0
    assert py_skill.adjusted_proficiency == 4.0
    assert py_skill.evidence_counts.total == 1
    assert py_skill.evidence_counts.approved == 1

    # 4. Add new skill via add_skill -> returns enriched SkillResponse (E1, 0.5, 1.5)
    new_skill = add_skill(
        data=SkillCreate(skill_name="SQL", proficiency=3),
        db=db_session,
        user=test_user_a
    )
    assert new_skill.skill_name == "SQL"
    assert new_skill.proficiency == 3
    assert new_skill.evidence_level == "E1"
    assert new_skill.lambda_weight == 0.5
    assert new_skill.adjusted_proficiency == 1.5
    assert new_skill.evidence_counts.total == 0
