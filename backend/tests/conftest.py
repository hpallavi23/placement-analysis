"""Shared Pytest Configuration and Test Fixtures for NXTSTEP.

Configures:
- An isolated in-memory SQLite database (sqlite:///:memory:) with StaticPool
- Automatic creation and cleanup of SQLAlchemy tables via Base.metadata
- FastAPI dependency override for get_db
- Reusable fixtures for database sessions, TestClient, test users, and JWT headers
"""

import sys
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend/ is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.security import create_access_token, hash_password
from app.db.database import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User

# In-memory test SQLite database engine (strictly isolated from nxtstep.db)
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)

# Initialize in-memory tables on test engine
Base.metadata.create_all(bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all database tables once for the test session and tear down at the end."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a transactional in-memory database session for a single test.

    Cleans data from all tables after each test to guarantee complete test isolation.
    """
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        # Clean data from all tables to maintain isolation across test runs
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with get_db overridden to use the in-memory test database."""

    def override_get_db() -> Generator[Session, None, None]:
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app, raise_server_exceptions=True)
    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def test_user_a(db_session: Session) -> User:
    """Create and return authenticated test user A in the isolated test database."""
    user = User(
        email="test_user_a@example.com",
        hashed_password=hash_password("Password123!"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_user_b(db_session: Session) -> User:
    """Create and return authenticated test user B in the isolated test database."""
    user = User(
        email="test_user_b@example.com",
        hashed_password=hash_password("Password456!"),
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers_a(test_user_a: User) -> dict[str, str]:
    """Generate valid JWT Authorization header for test user A."""
    token = create_access_token(data={"sub": str(test_user_a.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_b(test_user_b: User) -> dict[str, str]:
    """Generate valid JWT Authorization header for test user B."""
    token = create_access_token(data={"sub": str(test_user_b.id)})
    return {"Authorization": f"Bearer {token}"}
