import os
import sys
from dataclasses import dataclass

@dataclass
class Settings:
    PROJECT_NAME: str = "Ordexa"
    TAGLINE: str = "Know which products make money."
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development")).lower()

    # Auth
    _secret_key_raw = os.getenv("SECRET_KEY")
    if ENVIRONMENT == "production":
        if not _secret_key_raw or _secret_key_raw.strip() in [
            "",
            "profitpilot-super-secret-production-key-2026-safe",
            "ordexa-dev-secret-key-local-only-2026",
            "change-me",
            "secret"
        ]:
            raise RuntimeError(
                "FATAL: In production mode, SECRET_KEY environment variable is required and must not use an insecure default."
            )
        SECRET_KEY: str = _secret_key_raw.strip()
    else:
        SECRET_KEY: str = _secret_key_raw.strip() if _secret_key_raw else "ordexa-dev-secret-key-local-only-2026"

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 1

    # Database
    _db_url_raw = os.getenv("DATABASE_URL")
    if ENVIRONMENT == "production":
        if not _db_url_raw or not _db_url_raw.strip() or _db_url_raw.startswith("sqlite"):
            raise RuntimeError(
                "FATAL: In production mode, DATABASE_URL environment variable is required and must be a valid PostgreSQL connection string."
            )
        db_url = _db_url_raw.strip()
    else:
        db_url = _db_url_raw.strip() if _db_url_raw else f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'profitpilot.db')}"

    # Normalize PostgreSQL URL scheme for SQLAlchemy (psycopg2)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    DATABASE_URL: str = db_url

    # Storage
    STORAGE_PROVIDER: str = os.getenv("STORAGE_PROVIDER", "local").lower()
    STORAGE_DIR: str = os.path.abspath(os.getenv("STORAGE_DIR", "./uploads"))
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))

    # S3 Object Storage Settings (for production cloud storage)
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "")
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "")
    S3_ACCESS_KEY_ID: str = os.getenv("S3_ACCESS_KEY_ID", "")
    S3_SECRET_ACCESS_KEY: str = os.getenv("S3_SECRET_ACCESS_KEY", "")
    S3_REGION_NAME: str = os.getenv("S3_REGION_NAME", "us-east-1")

    # Email Service (for password reset)
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "pending_configuration")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "security@ordexa.com")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # AI Engine
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

settings = Settings()

os.makedirs(settings.STORAGE_DIR, exist_ok=True)
