from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
ROOT_DIR = BASE_DIR.parent                               # placement-analysis/

ENV_FILE = BASE_DIR / ".env" if (BASE_DIR / ".env").exists() else ROOT_DIR / ".env"
DEFAULT_DB_FILE = (ROOT_DIR / "nxtstep.db").resolve()
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DB_FILE.as_posix()}"

# Explicit development origins for React (3000), Vite (5173), and Live Server (5500)
DEFAULT_CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
]


class Settings(BaseSettings):
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    database_url: str = DEFAULT_DATABASE_URL
    cors_origins: str = ""
    reviewer_emails: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if isinstance(v, str):
            trimmed = v.strip()
            # Normalize legacy 'postgres://' scheme to SQLAlchemy-compatible 'postgresql://'
            if trimmed.startswith("postgres://"):
                return "postgresql://" + trimmed[len("postgres://"):]
            return trimmed
        return v

    @property
    def allowed_origins(self) -> list[str]:
        origins = list(DEFAULT_CORS_ORIGINS)
        if self.cors_origins:
            for item in self.cors_origins.split(","):
                cleaned = item.strip().rstrip("/")
                if cleaned and cleaned not in origins:
                    origins.append(cleaned)
        return origins

    @property
    def allowed_reviewer_emails(self) -> set[str]:
        if not self.reviewer_emails:
            return set()
        return {
            email.strip().lower()
            for email in self.reviewer_emails.split(",")
            if email.strip()
        }

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
