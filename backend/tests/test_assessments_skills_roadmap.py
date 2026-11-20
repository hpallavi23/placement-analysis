"""Automated Tests for Assessments, Skills, and Learning Roadmap Modules.

Coverage:
- Assessment creation, calculation of readiness score, and validation
- Assessment latest and history retrieval (including 404 on absent)
- Assessment user isolation
- Skill addition, retrieval, proficiency updating, and deletion
- Skill schema validation (proficiency boundaries 0-5, name length)
- Skill gap analysis for supported roles and 404 for unsupported roles
- Skill roles listing
- Roadmap generation for supported roles and gap task creation
- Roadmap retrieval and 404 handling
- Roadmap task completion lifecycle
- Strict cross-user isolation for skills and roadmap tasks (no cross-tenant visibility or modification)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


# ============================================================================
# Assessment Tests
# ============================================================================

def test_create_assessment_valid(client: TestClient, test_user_a: User, auth_headers_a: dict):
    """Verify submitting a valid assessment calculates the mean readiness score."""
    payload = {
        "aptitude_score": 80.0,
        "technical_score": 90.0,
        "communication_score": 70.0,
        "problem_solving_score": 80.0,
    }
    response = client.post("/api/v1/assessments/", json=payload, headers=auth_headers_a)
    assert response.status_code == 201

    data = response.json()
    assert data["user_id"] == test_user_a.id
    assert data["aptitude_score"] == 80.0
    assert data["technical_score"] == 90.0
    assert data["communication_score"] == 70.0
    assert data["problem_solving_score"] == 80.0
    # Expected readiness: (80 + 90 + 70 + 80) / 4 = 80.0
    assert data["readiness_score"] == 80.0
    assert "id" in data
    assert "created_at" in data


def test_create_assessment_invalid_scores(client: TestClient, auth_headers_a: dict):
    """Verify that score values exceeding bounds (<0 or >100) are rejected with 422."""
    # Score > 100
    res_high = client.post(
        "/api/v1/assessments/",
        json={
            "aptitude_score": 105.0,
            "technical_score": 80.0,
            "communication_score": 75.0,
            "problem_solving_score": 80.0,
        },
        headers=auth_headers_a,
    )
    assert res_high.status_code == 422

    # Score < 0
    res_low = client.post(
        "/api/v1/assessments/",
        json={
            "aptitude_score": -10.0,
            "technical_score": 80.0,
            "communication_score": 75.0,
            "problem_solving_score": 80.0,
        },
        headers=auth_headers_a,
    )
    assert res_low.status_code == 422


def test_get_latest_assessment(client: TestClient, auth_headers_a: dict):
    """Verify /assessments/latest returns 404 when absent, and returns latest when populated."""
    # 1. Absent initially -> 404
    res_empty = client.get("/api/v1/assessments/latest", headers=auth_headers_a)
    assert res_empty.status_code == 404
    assert "no assessment found" in res_empty.json()["detail"].lower()

    # 2. Add first assessment (readiness 60.0)
    client.post(
        "/api/v1/assessments/",
        json={
            "aptitude_score": 60.0,
            "technical_score": 60.0,
            "communication_score": 60.0,
            "problem_solving_score": 60.0,
        },
        headers=auth_headers_a,
    )

    # 3. Add second assessment (readiness 85.0)
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

    # 4. /latest should return second assessment
    res_latest = client.get("/api/v1/assessments/latest", headers=auth_headers_a)
    assert res_latest.status_code == 200
    assert res_latest.json()["readiness_score"] == 85.0


def test_get_assessment_history(client: TestClient, auth_headers_a: dict):
    """Verify /assessments/history returns an ordered list of student assessments."""
    # Empty history
    res_init = client.get("/api/v1/assessments/history", headers=auth_headers_a)
    assert res_init.status_code == 200
    assert res_init.json() == []

    # Submit 2 assessments
    for score in [70.0, 90.0]:
        client.post(
            "/api/v1/assessments/",
            json={
                "aptitude_score": score,
                "technical_score": score,
                "communication_score": score,
                "problem_solving_score": score,
            },
            headers=auth_headers_a,
        )

    res_history = client.get("/api/v1/assessments/history", headers=auth_headers_a)
    assert res_history.status_code == 200
    history_data = res_history.json()
    assert len(history_data) == 2
    # First item should be the latest assessment (descending order)
    assert history_data[0]["readiness_score"] == 90.0
    assert history_data[1]["readiness_score"] == 70.0


def test_assessment_user_isolation(
    client: TestClient,
    auth_headers_a: dict,
    auth_headers_b: dict,
):
    """Verify User A's assessments are invisible to User B."""
    # User A creates an assessment
    client.post(
        "/api/v1/assessments/",
        json={
            "aptitude_score": 95.0,
            "technical_score": 95.0,
            "communication_score": 95.0,
            "problem_solving_score": 95.0,
        },
        headers=auth_headers_a,
    )

    # User B checks latest -> 404
    res_b_latest = client.get("/api/v1/assessments/latest", headers=auth_headers_b)
    assert res_b_latest.status_code == 404

    # User B checks history -> empty list
    res_b_history = client.get("/api/v1/assessments/history", headers=auth_headers_b)
    assert res_b_history.status_code == 200
    assert res_b_history.json() == []


# ============================================================================
# Skills Tests
# ============================================================================

def test_skills_lifecycle(client: TestClient, test_user_a: User, auth_headers_a: dict):
    """Verify skill creation, list retrieval, proficiency update, and deletion."""
    # 1. List skills initially empty
    res_empty = client.get("/api/v1/skills/", headers=auth_headers_a)
    assert res_empty.status_code == 200
    assert res_empty.json() == []

    # 2. Add a skill
    payload = {"skill_name": "Python", "proficiency": 3}
    res_add = client.post("/api/v1/skills/", json=payload, headers=auth_headers_a)
    assert res_add.status_code == 200
    skill_data = res_add.json()
    assert skill_data["skill_name"] == "Python"
    assert skill_data["proficiency"] == 3
    assert skill_data["user_id"] == test_user_a.id
    skill_id = skill_data["id"]

    # 3. Retrieve skills
    res_list = client.get("/api/v1/skills/", headers=auth_headers_a)
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1

    # 4. Upsert/Update skill proficiency (case-insensitive match)
    update_payload = {"skill_name": "python", "proficiency": 5}
    res_update = client.post("/api/v1/skills/", json=update_payload, headers=auth_headers_a)
    assert res_update.status_code == 200
    assert res_update.json()["id"] == skill_id
    assert res_update.json()["proficiency"] == 5

    # Verify count remains 1 and proficiency updated
    res_list_after = client.get("/api/v1/skills/", headers=auth_headers_a)
    assert len(res_list_after.json()) == 1
    assert res_list_after.json()[0]["proficiency"] == 5

    # 5. Delete skill
    res_del = client.delete(f"/api/v1/skills/{skill_id}", headers=auth_headers_a)
    assert res_del.status_code == 200
    assert "deleted successfully" in res_del.json()["message"].lower()

    # Verify list is empty
    res_final = client.get("/api/v1/skills/", headers=auth_headers_a)
    assert res_final.json() == []


def test_skills_validation(client: TestClient, auth_headers_a: dict):
    """Verify validation boundaries on skill payload: proficiency 0-5 and name length."""
    # Proficiency > 5
    res_high = client.post(
        "/api/v1/skills/",
        json={"skill_name": "Python", "proficiency": 6},
        headers=auth_headers_a,
    )
    assert res_high.status_code == 422

    # Proficiency < 0
    res_low = client.post(
        "/api/v1/skills/",
        json={"skill_name": "Python", "proficiency": -1},
        headers=auth_headers_a,
    )
    assert res_low.status_code == 422

    # Skill name too short (< 2 characters)
    res_short = client.post(
        "/api/v1/skills/",
        json={"skill_name": "C", "proficiency": 3},
        headers=auth_headers_a,
    )
    assert res_short.status_code == 422


def test_skills_delete_nonexistent_or_unauthorized(
    client: TestClient,
    auth_headers_a: dict,
    auth_headers_b: dict,
):
    """Verify that deleting nonexistent skills or other users' skills returns 404."""
    # Delete nonexistent ID
    res_nonexistent = client.delete("/api/v1/skills/9999", headers=auth_headers_a)
    assert res_nonexistent.status_code == 404

    # User A creates a skill
    res_create = client.post(
        "/api/v1/skills/",
        json={"skill_name": "SQL", "proficiency": 4},
        headers=auth_headers_a,
    )
    skill_a_id = res_create.json()["id"]

    # User B attempts to delete User A's skill
    res_b_del = client.delete(f"/api/v1/skills/{skill_a_id}", headers=auth_headers_b)
    assert res_b_del.status_code == 404

    # Confirm User A's skill is still present
    res_a_check = client.get("/api/v1/skills/", headers=auth_headers_a)
    assert len(res_a_check.json()) == 1
    assert res_a_check.json()[0]["id"] == skill_a_id


def test_skills_roles_and_gap_analysis(client: TestClient, auth_headers_a: dict):
    """Verify supported roles listing and skill gap analysis computation."""
    # 1. Supported roles listing
    res_roles = client.get("/api/v1/skills/roles", headers=auth_headers_a)
    assert res_roles.status_code == 200
    roles = res_roles.json()
    assert isinstance(roles, list)
    assert "backend developer" in roles
    assert "frontend developer" in roles

    # 2. Add skills for user
    client.post("/api/v1/skills/", json={"skill_name": "Python", "proficiency": 4}, headers=auth_headers_a)
    client.post("/api/v1/skills/", json={"skill_name": "SQL", "proficiency": 4}, headers=auth_headers_a)

    # 3. Gap analysis for supported role
    res_gap = client.get("/api/v1/skills/gap/backend-developer", headers=auth_headers_a)
    assert res_gap.status_code == 200
    gap_data = res_gap.json()
    assert gap_data["role"].lower() == "backend developer"
    assert "readiness_percentage" in gap_data
    assert "skills" in gap_data
    assert isinstance(gap_data["skills"], list)
    assert isinstance(gap_data["readiness_percentage"], (int, float))

    # 4. Gap analysis for unsupported role returns 404
    res_unsupported = client.get("/api/v1/skills/gap/unsupported-quantum-engineer", headers=auth_headers_a)
    assert res_unsupported.status_code == 404
    assert "not supported" in res_unsupported.json()["detail"].lower()


# ============================================================================
# Roadmap Tests
# ============================================================================

def test_roadmap_generation_and_retrieval(client: TestClient, auth_headers_a: dict):
    """Verify personalized roadmap generation based on missing/gap skills."""
    # User A adds partial skill for "backend developer" (requires: Python:4, SQL:4, FastAPI:3, REST APIs:4, Git:2)
    client.post("/api/v1/skills/", json={"skill_name": "Python", "proficiency": 4}, headers=auth_headers_a)
    client.post("/api/v1/skills/", json={"skill_name": "SQL", "proficiency": 4}, headers=auth_headers_a)

    # Generate roadmap for backend developer
    res_gen = client.post("/api/v1/roadmaps/backend-developer/generate", headers=auth_headers_a)
    assert res_gen.status_code == 200
    tasks = res_gen.json()
    assert isinstance(tasks, list)
    assert len(tasks) > 0

    # Skills with 0 proficiency (FastAPI, REST APIs, Git) must have roadmap tasks
    task_skills = [t["skill_name"] for t in tasks]
    assert "FastAPI" in task_skills
    assert "REST APIs" in task_skills
    assert "Git" in task_skills
    # Fully matched skills (Python: 4, SQL: 4) should not require gap tasks
    assert "Python" not in task_skills
    assert "SQL" not in task_skills

    # Retrieve roadmap via GET
    res_get = client.get("/api/v1/roadmaps/backend-developer", headers=auth_headers_a)
    assert res_get.status_code == 200
    assert len(res_get.json()) == len(tasks)

    # Unsupported role returns 404
    res_bad_gen = client.post("/api/v1/roadmaps/unknown-role/generate", headers=auth_headers_a)
    assert res_bad_gen.status_code == 404

    res_bad_get = client.get("/api/v1/roadmaps/unknown-role", headers=auth_headers_a)
    assert res_bad_get.status_code == 404


def test_roadmap_task_completion_lifecycle(client: TestClient, auth_headers_a: dict):
    """Verify marking a roadmap task as completed updates its status."""
    # Generate roadmap for frontend developer
    res_gen = client.post("/api/v1/roadmaps/frontend-developer/generate", headers=auth_headers_a)
    assert res_gen.status_code == 200
    tasks = res_gen.json()
    assert len(tasks) > 0

    target_task = tasks[0]
    assert target_task["is_completed"] is False
    task_id = target_task["id"]

    # Mark completed
    res_complete = client.put(f"/api/v1/roadmaps/tasks/{task_id}/complete", headers=auth_headers_a)
    assert res_complete.status_code == 200
    complete_data = res_complete.json()
    assert complete_data["task"]["is_completed"] is True
    assert "completed successfully" in complete_data["message"].lower()

    # Attempt to complete nonexistent task ID returns 404
    res_nonexistent = client.put("/api/v1/roadmaps/tasks/99999/complete", headers=auth_headers_a)
    assert res_nonexistent.status_code == 404


def test_roadmap_user_isolation(
    client: TestClient,
    auth_headers_a: dict,
    auth_headers_b: dict,
):
    """Verify User B cannot see or complete User A's roadmap tasks."""
    # User A generates a roadmap
    res_gen = client.post("/api/v1/roadmaps/frontend-developer/generate", headers=auth_headers_a)
    tasks_a = res_gen.json()
    assert len(tasks_a) > 0
    task_a_id = tasks_a[0]["id"]

    # User B queries the roadmap for the same role -> should be empty for User B
    res_b_roadmap = client.get("/api/v1/roadmaps/frontend-developer", headers=auth_headers_b)
    assert res_b_roadmap.status_code == 200
    assert res_b_roadmap.json() == []

    # User B attempts to complete User A's task -> 404 Not Found
    res_b_complete = client.put(f"/api/v1/roadmaps/tasks/{task_a_id}/complete", headers=auth_headers_b)
    assert res_b_complete.status_code == 404

    # Verify User A's task is still not completed
    res_a_roadmap = client.get("/api/v1/roadmaps/frontend-developer", headers=auth_headers_a)
    matched = [t for t in res_a_roadmap.json() if t["id"] == task_a_id]
    assert len(matched) == 1
    assert matched[0]["is_completed"] is False
