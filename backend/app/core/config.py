from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
ROOT_DIR = BASE_DIR.parent                               # placement-analysis/

ENV_FILE = BASE_DIR / ".env" if (BASE_DIR / ".env").exists() else ROOT_DIR / ".env"
DEFAULT_DB_FILE = (ROOT_DIR / "nxtstep.db").resolve()
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DB_FILE.as_posix()}"


class Settings(BaseSettings):
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    database_url: str = DEFAULT_DATABASE_URL
    reviewer_emails: str = ""

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
