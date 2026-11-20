"""Automated Tests for Authentication & Student Profile Modules.

Coverage:
- User registration with valid data
- Duplicate email registration rejection (HTTP 409)
- Login with valid credentials (OAuth2 form-data)
- Login with invalid credentials (HTTP 401)
- Authenticated /me endpoint access
- Unauthenticated access rejection on protected routes (HTTP 401)
- Student profile creation, retrieval, and partial updates
- Cross-user data isolation between User A and User B
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.student_profile import StudentProfile
from app.models.user import User


def test_register_valid_user(client: TestClient):
    """Verify that a new student can successfully register with valid credentials."""
    payload = {
        "email": "new_student@example.com",
        "password": "SecurePassword123!",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["email"] == "new_student@example.com"
    assert data["is_active"] is True
    assert "id" in data
    assert "hashed_password" not in data


def test_register_duplicate_email(client: TestClient, test_user_a: User):
    """Verify that registering with an already registered email is rejected with 409 Conflict."""
    payload = {
        "email": test_user_a.email,
        "password": "AnotherPassword123!",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    assert "already registered" in response.json()["detail"].lower()


def test_register_invalid_payload(client: TestClient):
    """Verify that invalid payloads (e.g. short password) are rejected with 422."""
    payload = {
        "email": "invalid_pwd@example.com",
        "password": "short",  # min_length is 8
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


def test_login_valid_credentials(client: TestClient, test_user_a: User):
    """Verify that a valid user can log in and receive an OAuth2 Bearer access token."""
    login_data = {
        "username": test_user_a.email,
        "password": "Password123!",
    }
    response = client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 20


def test_login_invalid_password(client: TestClient, test_user_a: User):
    """Verify that login with incorrect password returns 401 Unauthorized."""
    login_data = {
        "username": test_user_a.email,
        "password": "WrongPassword999!",
    }
    response = client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


def test_login_nonexistent_user(client: TestClient):
    """Verify that login with non-existent email returns 401 Unauthorized."""
    login_data = {
        "username": "ghost_user@example.com",
        "password": "Password123!",
    }
    response = client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 401


def test_get_my_account(client: TestClient, test_user_a: User, auth_headers_a: dict):
    """Verify that /auth/me returns the authenticated user's account details."""
    response = client.get("/api/v1/auth/me", headers=auth_headers_a)
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == test_user_a.id
    assert data["email"] == test_user_a.email
    assert data["is_active"] is True


def test_unauthenticated_protected_route_rejected(client: TestClient):
    """Verify that calling protected endpoints without credentials returns 401."""
    # /auth/me
    res_me = client.get("/api/v1/auth/me")
    assert res_me.status_code == 401

    # /profile/
    res_profile = client.get("/api/v1/profile/")
    assert res_profile.status_code == 401


def test_profile_lifecycle(client: TestClient, test_user_a: User, auth_headers_a: dict):
    """Verify complete profile lifecycle: 404 when absent -> create -> retrieve -> update."""
    # 1. Profile absent initially
    res_init = client.get("/api/v1/profile/", headers=auth_headers_a)
    assert res_init.status_code == 404

    # 2. Create student profile
    profile_payload = {
        "full_name": "Test Student A",
        "college": "Engineering College of Pune",
        "branch": "Computer Science",
        "graduation_year": 2026,
        "cgpa": 8.75,
    }
    res_create = client.post("/api/v1/profile/", json=profile_payload, headers=auth_headers_a)
    assert res_create.status_code == 201
    data_created = res_create.json()
    assert data_created["user_id"] == test_user_a.id
    assert data_created["full_name"] == "Test Student A"
    assert data_created["cgpa"] == 8.75

    # 3. Retrieve student profile
    res_get = client.get("/api/v1/profile/", headers=auth_headers_a)
    assert res_get.status_code == 200
    assert res_get.json()["full_name"] == "Test Student A"

    # 4. Partial update (change CGPA and graduation year)
    update_payload = {"cgpa": 9.10, "graduation_year": 2027}
    res_update = client.put("/api/v1/profile/", json=update_payload, headers=auth_headers_a)
    assert res_update.status_code == 200
    updated_data = res_update.json()
    assert updated_data["cgpa"] == 9.10
    assert updated_data["graduation_year"] == 2027
    assert updated_data["full_name"] == "Test Student A"  # preserved


def test_profile_duplicate_creation_rejected(client: TestClient, auth_headers_a: dict):
    """Verify that a user cannot create more than one profile (HTTP 409)."""
    payload = {"full_name": "First Profile", "cgpa": 8.0}
    res1 = client.post("/api/v1/profile/", json=payload, headers=auth_headers_a)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/profile/", json=payload, headers=auth_headers_a)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower()


def test_profile_user_isolation(
    client: TestClient,
    test_user_a: User,
    auth_headers_a: dict,
    test_user_b: User,
    auth_headers_b: dict,
):
    """Verify strict user isolation: User A's profile cannot be accessed or modified by User B."""
    # User A creates a profile
    payload_a = {
        "full_name": "Student A Private",
        "college": "Institute A",
        "cgpa": 8.9,
    }
    res_create = client.post("/api/v1/profile/", json=payload_a, headers=auth_headers_a)
    assert res_create.status_code == 201

    # User B checks their own profile -> must be 404 (User A's profile does not leak)
    res_b_get = client.get("/api/v1/profile/", headers=auth_headers_b)
    assert res_b_get.status_code == 404

    # User B attempts to update their profile -> must be 404 (cannot update non-existent profile)
    res_b_update = client.put("/api/v1/profile/", json={"cgpa": 7.0}, headers=auth_headers_b)
    assert res_b_update.status_code == 404

    # User A's profile remains unchanged
    res_a_check = client.get("/api/v1/profile/", headers=auth_headers_a)
    assert res_a_check.status_code == 200
    assert res_a_check.json()["full_name"] == "Student A Private"
    assert res_a_check.json()["cgpa"] == 8.9
