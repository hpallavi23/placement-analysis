"""Automated Tests for Analytics, Simulation & ML Placement Prediction Modules.

Coverage:
- Dashboard summary retrieval for empty state (graceful fallbacks)
- Dashboard summary for fully populated student profile, assessment, skills, and roadmap
- Dashboard user data isolation
- Placement opportunity matching across benchmark companies
- CGPA eligibility states (Eligible, Not Eligible, Unknown) and fit scoring
- Opportunity detail retrieval and 404 for invalid IDs
- What-If simulation engine in-memory execution and strict database immutability
- What-If input bounds validation (HTTP 422 on invalid ranges)
- Machine Learning placement prediction with explicit overrides
- Machine Learning placement prediction with auto-resolved profile and assessment features
- Soft skills rating conversion from assessment communication score
- Missing prerequisite validation (HTTP 400 when CGPA or assessment absent without override)
- Micro-fixed supplementary feature validation boundaries (internships le=2, projects le=3, workshops le=3)
- Prediction user data isolation
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.skill import Skill
from app.models.student_profile import StudentProfile
from app.models.user import User


# ============================================================================
# Dashboard Summary Tests
# ============================================================================

def test_dashboard_summary_empty_state(client: TestClient, test_user_a: User, auth_headers_a: dict):
    """Verify dashboard summary gracefully handles empty profile, assessment, and roadmap."""
    response = client.get("/api/v1/dashboard/summary", headers=auth_headers_a)
    assert response.status_code == 200

    data = response.json()
    assert data["student"]["user_id"] == test_user_a.id
    assert data["student"]["full_name"] is None
    assert data["student"]["cgpa"] is None
    assert data["readiness"]["has_assessment"] is False
    assert data["readiness"]["overall_readiness_score"] is None
    assert data["skills_overview"]["total_skills_logged"] == 0
    assert data["skills_overview"]["top_skills"] == []
    assert data["roadmap_progress"]["has_active_roadmap"] is False
    assert data["roadmap_progress"]["total_tasks"] == 0
    assert "complete your student profile" in data["recommended_next_action"].lower()


def test_dashboard_summary_populated_state(client: TestClient, auth_headers_a: dict):
    """Verify dashboard summary with populated profile, assessment, skills, and roadmap."""
    # 1. Profile
    client.post(
        "/api/v1/profile/",
        json={"full_name": "Active Student", "cgpa": 8.75, "branch": "Computer Science"},
        headers=auth_headers_a,
    )

    # 2. Assessment
    client.post(
        "/api/v1/assessments/",
        json={
            "aptitude_score": 85.0,
            "technical_score": 85.0,
            "communication_score": 85.0,
            "problem_solving_score": 85.0,
        },
        headers=auth_headers_a,
    )

    # 3. Skills
    client.post("/api/v1/skills/", json={"skill_name": "Python", "proficiency": 4}, headers=auth_headers_a)
    client.post("/api/v1/skills/", json={"skill_name": "SQL", "proficiency": 3}, headers=auth_headers_a)

    # 4. Roadmap
    client.post("/api/v1/roadmaps/backend-developer/generate", headers=auth_headers_a)

    # 5. Fetch dashboard summary
    response = client.get("/api/v1/dashboard/summary", headers=auth_headers_a)
    assert response.status_code == 200
    data = response.json()

    assert data["student"]["full_name"] == "Active Student"
    assert data["student"]["cgpa"] == 8.75
    assert data["readiness"]["has_assessment"] is True
    assert data["readiness"]["overall_readiness_score"] == 85.0
    assert data["skills_overview"]["total_skills_logged"] == 2
    assert len(data["skills_overview"]["top_skills"]) == 2
    assert data["roadmap_progress"]["has_active_roadmap"] is True
    assert data["roadmap_progress"]["active_role"].lower() == "backend developer"
    assert len(data["role_readiness"]) == 5
    assert data["best_fit_role"] is not None


def test_dashboard_user_isolation(
    client: TestClient,
    test_user_a: User,
    auth_headers_a: dict,
    test_user_b: User,
    auth_headers_b: dict,
):
    """Verify User A's dashboard data does not leak into User B's dashboard."""
    # User A populates profile and assessment
    client.post(
        "/api/v1/profile/",
        json={"full_name": "Student A Secret", "cgpa": 9.2},
        headers=auth_headers_a,
    )
    client.post(
        "/api/v1/assessments/",
        json={"aptitude_score": 90.0, "technical_score": 90.0, "communication_score": 90.0, "problem_solving_score": 90.0},
        headers=auth_headers_a,
    )

    # User B queries dashboard
    res_b = client.get("/api/v1/dashboard/summary", headers=auth_headers_b)
    assert res_b.status_code == 200
    data_b = res_b.json()

    assert data_b["student"]["user_id"] == test_user_b.id
    assert data_b["student"]["full_name"] is None
    assert data_b["readiness"]["has_assessment"] is False
    assert data_b["skills_overview"]["total_skills_logged"] == 0


# ============================================================================
# Placement Opportunity Analysis Tests
# ============================================================================

def test_opportunities_list_and_sorting(client: TestClient, auth_headers_a: dict):
    """Verify that opportunities returns all 8 benchmark items sorted by overall_fit_score descending."""
    client.post("/api/v1/profile/", json={"full_name": "Student A", "cgpa": 8.0}, headers=auth_headers_a)
    client.post("/api/v1/skills/", json={"skill_name": "Python", "proficiency": 4}, headers=auth_headers_a)

    response = client.get("/api/v1/opportunities/", headers=auth_headers_a)
    assert response.status_code == 200
    opportunities = response.json()

    assert len(opportunities) == 8
    scores = [opp["overall_fit_score"] for opp in opportunities]
    assert scores == sorted(scores, reverse=True)

    # Verify benchmark structure on all items
    for opp in opportunities:
        assert "id" in opp
        assert "company_name" in opp
        assert "package_lpa" in opp
        assert "cgpa_eligibility_status" in opp
        assert "benchmark_disclaimer" in opp


def test_opportunities_cgpa_eligibility_states(client: TestClient, auth_headers_a: dict):
    """Verify the three CGPA eligibility states: Unknown, Eligible, and Not Eligible."""
    # State 1: Unknown (no profile/CGPA provided)
    res_unknown = client.get("/api/v1/opportunities/", headers=auth_headers_a)
    assert res_unknown.status_code == 200
    first_item = res_unknown.json()[0]
    assert first_item["cgpa_eligibility_status"] == "Unknown (CGPA not provided)"
    assert first_item["is_eligible_cgpa"] is None

    # State 2: Eligible (CGPA 9.0 exceeds benchmark cutoffs e.g. 7.0)
    client.post("/api/v1/profile/", json={"full_name": "Student A", "cgpa": 9.0}, headers=auth_headers_a)
    res_eligible = client.get("/api/v1/opportunities/1", headers=auth_headers_a)
    assert res_eligible.status_code == 200
    data_el = res_eligible.json()
    assert data_el["cgpa_eligibility_status"] == "Eligible"
    assert data_el["is_eligible_cgpa"] is True

    # State 3: Not Eligible (CGPA 5.0 below benchmark cutoff 7.0)
    client.put("/api/v1/profile/", json={"cgpa": 5.0}, headers=auth_headers_a)
    res_ineligible = client.get("/api/v1/opportunities/1", headers=auth_headers_a)
    assert res_ineligible.status_code == 200
    data_in = res_ineligible.json()
    assert data_in["cgpa_eligibility_status"] == "Not Eligible"
    assert data_in["is_eligible_cgpa"] is False
    assert "below cutoff" in data_in["status"].lower()


def test_opportunity_detail_by_id(client: TestClient, auth_headers_a: dict):
    """Verify retrieving specific opportunities by ID and 404 for invalid ID."""
    # Valid ID
    res_valid = client.get("/api/v1/opportunities/2", headers=auth_headers_a)
    assert res_valid.status_code == 200
    assert res_valid.json()["id"] == 2
    assert "Infosys" in res_valid.json()["company_name"]

    # Invalid ID
    res_invalid = client.get("/api/v1/opportunities/999", headers=auth_headers_a)
    assert res_invalid.status_code == 404
    assert "not found" in res_invalid.json()["detail"].lower()


# ============================================================================
# What-If Simulation Tests
# ============================================================================

def test_what_if_simulation_in_memory_and_immutability(
    client: TestClient,
    test_user_a: User,
    auth_headers_a: dict,
    db_session: Session,
):
    """Verify what-if simulation calculates hypothetical metrics without modifying stored database records."""
    # 1. Establish baseline records
    client.post("/api/v1/profile/", json={"full_name": "Sim Student", "cgpa": 7.0}, headers=auth_headers_a)
    client.post(
        "/api/v1/assessments/",
        json={"aptitude_score": 60.0, "technical_score": 60.0, "communication_score": 60.0, "problem_solving_score": 60.0},
        headers=auth_headers_a,
    )
    client.post("/api/v1/skills/", json={"skill_name": "Python", "proficiency": 2}, headers=auth_headers_a)

    # Snapshot database counts before simulation
    profile_count_before = db_session.query(StudentProfile).count()
    assessment_count_before = db_session.query(Assessment).count()
    skill_count_before = db_session.query(Skill).count()

    # 2. Run simulation with hypothetical improvements
    sim_payload = {
        "target_role": "backend developer",
        "simulated_cgpa": 9.0,
        "simulated_aptitude": 85.0,
        "simulated_technical": 85.0,
        "simulated_communication": 85.0,
        "simulated_problem_solving": 85.0,
        "simulated_skills": {"Python": 5, "SQL": 4, "FastAPI": 3},
    }
    response = client.post("/api/v1/simulation/what-if", json=sim_payload, headers=auth_headers_a)
    assert response.status_code == 200

    data = response.json()
    assert data["readiness_score"]["current"] == 60.0
    assert data["readiness_score"]["simulated"] == 85.0
    assert data["readiness_score"]["delta"] == 25.0
    assert "opportunities_impact" in data
    assert "all_roles_readiness" in data
    assert len(data["all_roles_readiness"]) == 5
    assert len(data["insights"]) > 0

    # 3. Assert database immutability: table row counts and values must be identical
    assert db_session.query(StudentProfile).count() == profile_count_before
    assert db_session.query(Assessment).count() == assessment_count_before
    assert db_session.query(Skill).count() == skill_count_before

    # Verify actual baseline profile CGPA and skill proficiency were not overwritten
    stored_profile = db_session.query(StudentProfile).filter(StudentProfile.user_id == test_user_a.id).first()
    assert stored_profile.cgpa == 7.0

    stored_skill = db_session.query(Skill).filter(Skill.user_id == test_user_a.id, Skill.skill_name == "Python").first()
    assert stored_skill.proficiency == 2


def test_what_if_simulation_validation_errors(client: TestClient, auth_headers_a: dict):
    """Verify what-if simulation rejects out-of-bounds input values with 422."""
    # CGPA > 10.0
    res_bad_cgpa = client.post(
        "/api/v1/simulation/what-if",
        json={"simulated_cgpa": 11.5},
        headers=auth_headers_a,
    )
    assert res_bad_cgpa.status_code == 422

    # Aptitude > 100.0
    res_bad_apt = client.post(
        "/api/v1/simulation/what-if",
        json={"simulated_aptitude": 150.0},
        headers=auth_headers_a,
    )
    assert res_bad_apt.status_code == 422


# ============================================================================
# ML Placement Prediction Engine Tests
# ============================================================================

def test_prediction_endpoint_with_explicit_overrides(client: TestClient, auth_headers_a: dict):
    """Verify placement probability prediction endpoint using explicit request overrides."""
    payload = {
        "cgpa": 8.5,
        "aptitude_test_score": 82.0,
        "soft_skills_rating": 4.0,
        "internships": 1,
        "projects": 2,
        "workshops_certifications": 1,
        "extracurricular_activities": "Yes",
        "placement_training": "Yes",
        "ssc_marks": 85.0,
        "hsc_marks": 80.0,
    }
    response = client.post("/api/v1/predictions/placement-probability", json=payload, headers=auth_headers_a)
    assert response.status_code == 200

    data = response.json()
    assert 0.0 <= data["placement_probability"] <= 1.0
    assert 0.0 <= data["placement_probability_pct"] <= 100.0
    assert data["predicted_class"] in ("Placed", "NotPlaced")
    assert data["prediction_label"] in (0, 1)
    assert "LogisticRegression" in data["model_name"]
    assert data["input_features_used"]["CGPA"] == 8.5
    assert data["input_features_used"]["AptitudeTestScore"] == 82.0
    assert data["input_features_used"]["SoftSkillsRating"] == 4.0
    assert "disclaimer" in data
    assert "technical_readiness_note" in data


def test_prediction_auto_resolving_from_profile_and_assessment(client: TestClient, auth_headers_a: dict):
    """Verify placement prediction auto-resolves CGPA, Aptitude, and converts Soft Skills."""
    # 1. Populate profile with CGPA 8.2
    client.post("/api/v1/profile/", json={"full_name": "Student A", "cgpa": 8.2}, headers=auth_headers_a)

    # 2. Populate assessment with aptitude 75.0 and communication 80.0
    # Soft skills converted = 1.0 + (80.0 / 100.0) * 4.0 = 4.2
    client.post(
        "/api/v1/assessments/",
        json={
            "aptitude_score": 75.0,
            "technical_score": 80.0,
            "communication_score": 80.0,
            "problem_solving_score": 80.0,
        },
        headers=auth_headers_a,
    )

    # 3. Call prediction without cgpa, aptitude_test_score, soft_skills_rating
    payload = {
        "internships": 2,
        "projects": 3,
        "workshops_certifications": 2,
        "extracurricular_activities": "No",
        "placement_training": "Yes",
        "ssc_marks": 78.5,
        "hsc_marks": 72.0,
    }
    response = client.post("/api/v1/predictions/placement-probability", json=payload, headers=auth_headers_a)
    assert response.status_code == 200

    data = response.json()
    assert data["input_features_used"]["CGPA"] == 8.2
    assert data["input_features_used"]["AptitudeTestScore"] == 75.0
    assert data["input_features_used"]["SoftSkillsRating"] == 4.2


def test_prediction_missing_prerequisites_error(client: TestClient, auth_headers_a: dict):
    """Verify that omitting CGPA without a student profile returns 400 Bad Request."""
    payload = {
        "aptitude_test_score": 80.0,
        "soft_skills_rating": 4.0,
        "internships": 1,
        "projects": 2,
        "workshops_certifications": 1,
        "extracurricular_activities": "Yes",
        "placement_training": "Yes",
        "ssc_marks": 85.0,
        "hsc_marks": 80.0,
    }
    response = client.post("/api/v1/predictions/placement-probability", json=payload, headers=auth_headers_a)
    assert response.status_code == 400
    assert "cgpa is required" in response.json()["detail"].lower()


def test_prediction_validation_bounds(client: TestClient, auth_headers_a: dict):
    """Verify validation boundary enforcement on supplementary features (internships le=2, projects le=3, workshops le=3)."""
    client.post("/api/v1/profile/", json={"full_name": "Student A", "cgpa": 8.0}, headers=auth_headers_a)
    client.post(
        "/api/v1/assessments/",
        json={"aptitude_score": 80.0, "technical_score": 80.0, "communication_score": 80.0, "problem_solving_score": 80.0},
        headers=auth_headers_a,
    )

    base_payload = {
        "internships": 1,
        "projects": 2,
        "workshops_certifications": 1,
        "extracurricular_activities": "Yes",
        "placement_training": "Yes",
        "ssc_marks": 85.0,
        "hsc_marks": 80.0,
    }

    # Internships > 2 (boundary violation)
    res_bad_int = client.post(
        "/api/v1/predictions/placement-probability",
        json={**base_payload, "internships": 3},
        headers=auth_headers_a,
    )
    assert res_bad_int.status_code == 422

    # Projects > 3 (boundary violation)
    res_bad_proj = client.post(
        "/api/v1/predictions/placement-probability",
        json={**base_payload, "projects": 4},
        headers=auth_headers_a,
    )
    assert res_bad_proj.status_code == 422

    # Workshops > 3 (boundary violation)
    res_bad_work = client.post(
        "/api/v1/predictions/placement-probability",
        json={**base_payload, "workshops_certifications": 4},
        headers=auth_headers_a,
    )
    assert res_bad_work.status_code == 422


def test_prediction_user_isolation(
    client: TestClient,
    auth_headers_a: dict,
    auth_headers_b: dict,
):
    """Verify prediction endpoint uses the authenticated user's own profile and assessment."""
    # User A: CGPA 9.5, Aptitude 90.0
    client.post("/api/v1/profile/", json={"full_name": "Student A", "cgpa": 9.5}, headers=auth_headers_a)
    client.post(
        "/api/v1/assessments/",
        json={"aptitude_score": 90.0, "technical_score": 90.0, "communication_score": 90.0, "problem_solving_score": 90.0},
        headers=auth_headers_a,
    )

    # User B: CGPA 6.5, Aptitude 60.0
    client.post("/api/v1/profile/", json={"full_name": "Student B", "cgpa": 6.5}, headers=auth_headers_b)
    client.post(
        "/api/v1/assessments/",
        json={"aptitude_score": 60.0, "technical_score": 60.0, "communication_score": 60.0, "problem_solving_score": 60.0},
        headers=auth_headers_b,
    )

    shared_supplementary = {
        "internships": 1,
        "projects": 2,
        "workshops_certifications": 1,
        "extracurricular_activities": "Yes",
        "placement_training": "Yes",
        "ssc_marks": 80.0,
        "hsc_marks": 75.0,
    }

    res_a = client.post("/api/v1/predictions/placement-probability", json=shared_supplementary, headers=auth_headers_a)
    assert res_a.status_code == 200
    assert res_a.json()["input_features_used"]["CGPA"] == 9.5
    assert res_a.json()["input_features_used"]["AptitudeTestScore"] == 90.0

    res_b = client.post("/api/v1/predictions/placement-probability", json=shared_supplementary, headers=auth_headers_b)
    assert res_b.status_code == 200
    assert res_b.json()["input_features_used"]["CGPA"] == 6.5
    assert res_b.json()["input_features_used"]["AptitudeTestScore"] == 60.0
