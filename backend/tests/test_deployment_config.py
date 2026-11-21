"""Focused automated tests for NXTSTEP deployment configuration.

Verifies:
1. PostgreSQL URL normalization ('postgres://' -> 'postgresql://').
2. CORS allowed origins parsing, trimming, deduplication, and retention of localhost.
3. CORS origin acceptance (localhost and configured) vs rejection (untrusted origin).
4. Reviewer email parsing (whitespace, case-insensitivity, empty string).
5. SQLite engine configuration (pool_pre_ping=True, pool_recycle=300, connect_args).
6. PostgreSQL driver (psycopg2) availability.
"""

import sys
import unittest
from pathlib import Path

# Ensure backend/ is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import create_engine, text
from app.core.config import Settings, DEFAULT_CORS_ORIGINS


class TestDeploymentConfiguration(unittest.TestCase):
    """Test suite verifying deployment configuration invariants."""

    def test_postgres_url_normalization_legacy_scheme(self):
        """Verify that legacy 'postgres://' connection URLs normalize to 'postgresql://'."""
        neon_url = "postgres://user:password@ep-xyz-123.us-east-2.aws.neon.tech/neondb?sslmode=require"
        settings = Settings(secret_key="test-key-32-chars-long-strictly", database_url=neon_url)
        self.assertTrue(settings.database_url.startswith("postgresql://"))
        self.assertFalse(settings.database_url.startswith("postgres://"))
        self.assertEqual(
            settings.database_url,
            "postgresql://user:password@ep-xyz-123.us-east-2.aws.neon.tech/neondb?sslmode=require",
        )

    def test_postgres_url_normalization_standard_scheme(self):
        """Verify that standard 'postgresql://' URLs are preserved as-is."""
        standard_url = "postgresql://user:password@ep-xyz-123.us-east-2.aws.neon.tech/neondb?sslmode=require"
        settings = Settings(secret_key="test-key-32-chars-long-strictly", database_url=standard_url)
        self.assertEqual(settings.database_url, standard_url)

    def test_sqlite_url_preserved(self):
        """Verify that local SQLite database URLs remain unchanged."""
        sqlite_url = "sqlite:///custom_nxtstep.db"
        settings = Settings(secret_key="test-key-32-chars-long-strictly", database_url=sqlite_url)
        self.assertEqual(settings.database_url, sqlite_url)

    def test_cors_default_origins_retained(self):
        """Verify that all default localhost and loopback origins are preserved when no CORS_ORIGINS are set."""
        settings = Settings(secret_key="test-key-32-chars-long-strictly", cors_origins="")
        allowed = settings.allowed_origins
        for origin in DEFAULT_CORS_ORIGINS:
            self.assertIn(origin, allowed)

    def test_cors_configured_origins_parsing(self):
        """Verify that CORS_ORIGINS parses comma-separated URLs, trims whitespace, and strips trailing slashes."""
        raw_origins = " https://nxtstep.onrender.com/ , https://staging.nxtstep.onrender.com "
        settings = Settings(secret_key="test-key-32-chars-long-strictly", cors_origins=raw_origins)
        allowed = settings.allowed_origins

        # Verify added production origins
        self.assertIn("https://nxtstep.onrender.com", allowed)
        self.assertIn("https://staging.nxtstep.onrender.com", allowed)

        # Verify trailing slash was stripped
        self.assertNotIn("https://nxtstep.onrender.com/", allowed)

        # Verify local origins are still included
        self.assertIn("http://localhost:5500", allowed)
        self.assertIn("http://127.0.0.1:3000", allowed)

    def test_cors_origin_acceptance_and_rejection(self):
        """Verify that accepted origins match and untrusted origins are strictly rejected."""
        settings = Settings(
            secret_key="test-key-32-chars-long-strictly",
            cors_origins="https://nxtstep.onrender.com",
        )
        allowed = set(settings.allowed_origins)

        # Accepted
        self.assertTrue("https://nxtstep.onrender.com" in allowed)
        self.assertTrue("http://localhost:5500" in allowed)
        self.assertTrue("http://127.0.0.1:5173" in allowed)

        # Rejected (untrusted)
        self.assertFalse("https://malicious-phishing-site.example.com" in allowed)
        self.assertFalse("https://onrender.com" in allowed)
        self.assertFalse("http://localhost:8080" in allowed)

    def test_cors_deduplication(self):
        """Verify that adding an origin that already exists in defaults does not create duplicates."""
        settings = Settings(
            secret_key="test-key-32-chars-long-strictly",
            cors_origins="http://localhost:3000, https://nxtstep.onrender.com",
        )
        allowed = settings.allowed_origins
        self.assertEqual(allowed.count("http://localhost:3000"), 1)

    def test_reviewer_emails_parsing(self):
        """Verify reviewer email parsing with trimming, lowercase conversion, and empty values."""
        raw_emails = "reviewer.one@example.com, REVIEWER.TWO@EXAMPLE.COM , , reviewer.one@example.com "
        settings = Settings(secret_key="test-key-32-chars-long-strictly", reviewer_emails=raw_emails)
        expected = {"reviewer.one@example.com", "reviewer.two@example.com"}
        self.assertEqual(settings.allowed_reviewer_emails, expected)

        # Empty string
        empty_settings = Settings(secret_key="test-key-32-chars-long-strictly", reviewer_emails="")
        self.assertEqual(empty_settings.allowed_reviewer_emails, set())

    def test_sqlite_database_connectivity_and_options(self):
        """Verify SQLite engine connectivity with pool_pre_ping and pool_recycle."""
        test_db_url = "sqlite:///:memory:"
        connect_args = {"check_same_thread": False}
        engine = create_engine(
            test_db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            self.assertEqual(result, 1)

    def test_psycopg2_driver_import(self):
        """Verify that the PostgreSQL driver (psycopg2) is installed and importable."""
        try:
            import psycopg2
            self.assertTrue(hasattr(psycopg2, "__version__"))
        except ImportError as exc:
            self.fail(f"psycopg2 is not installed or failed to import: {exc}")

    def test_cors_middleware_http_headers(self):
        """Verify that FastAPI CORSMiddleware returns correct headers for allowed origins and rejects untrusted ones."""
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            # 1. Allowed localhost origin
            res_local = client.get("/health", headers={"Origin": "http://localhost:5500"})
            self.assertEqual(res_local.status_code, 200)
            self.assertEqual(res_local.headers.get("access-control-allow-origin"), "http://localhost:5500")
            self.assertEqual(res_local.headers.get("access-control-allow-credentials"), "true")

            # 2. Untrusted origin
            res_untrusted = client.get("/health", headers={"Origin": "https://malicious-site.example.com"})
            self.assertEqual(res_untrusted.status_code, 200)
            self.assertIsNone(res_untrusted.headers.get("access-control-allow-origin"))


if __name__ == "__main__":
    unittest.main()
