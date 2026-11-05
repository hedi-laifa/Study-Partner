"""Core configuration and environment variable validation."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application settings loaded and validated from environment variables or .env file."""

    APP_NAME: str = Field(default="Study Partner AI", min_length=1)
    APP_ENV: Literal["development", "testing", "staging", "production"] = "development"
    APP_DEBUG: bool = True
    APP_VERSION: str = "0.4.0"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    API_V1_PREFIX: str = "/api/v1"

    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = Field(default=8000, ge=1, le=65535)
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    POSTGRES_USER: str = Field(default="studypartner", min_length=1)
    POSTGRES_PASSWORD: str = Field(default="studypartner_dev_password", min_length=1)
    POSTGRES_HOST: str = Field(default="localhost", min_length=1)
    POSTGRES_PORT: int = Field(default=5432, ge=1, le=65535)
    POSTGRES_DB: str = Field(default="study_partner_db", min_length=1)
    DATABASE_URL: str = (
        "postgresql+psycopg://studypartner:studypartner_dev_password@localhost:5432/study_partner_db"
    )
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = Field(default=5, ge=1, le=100)
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0, le=100)

    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = Field(default=8001, ge=1, le=65535)
    CHROMA_PERSIST_DIR: str = str(REPO_ROOT / "storage" / "chroma")
    CHROMA_COLLECTION_NAME: str = Field(default="study_partner_chunks", min_length=1)

    UPLOAD_STORAGE_DIR: str = str(REPO_ROOT / "storage" / "uploads")
    MAX_UPLOAD_SIZE_MB: int = Field(default=50, ge=1, le=500)

    # AI, Embeddings & Retrieval Settings
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434", min_length=1)
    OLLAMA_MODEL: str = Field(default="llama3.1:8b", min_length=1)
    OLLAMA_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0.0, le=300.0)
    TUTOR_OFFLINE_FALLBACK: bool = Field(
        default=False,
        description="If true, synthesize strictly grounded extractive answers when Ollama is unreachable",
    )

    EMBEDDING_MODEL_NAME: str = Field(default="all-MiniLM-L6-v2", min_length=1)
    EMBEDDING_DIMENSION: int = Field(default=384, ge=32, le=4096)
    RETRIEVAL_TOP_K: int = Field(default=5, ge=1, le=20)
    RETRIEVAL_MIN_SCORE: float = Field(default=0.18, ge=0.0, le=1.0)

    # Authentication Settings (stdlib HMAC-SHA256 signed bearer tokens)
    AUTH_SECRET_KEY: str = Field(
        default="dev-only-insecure-secret-change-me-in-production",
        min_length=16,
        description="Secret used to sign access tokens. MUST be overridden outside development.",
    )
    AUTH_TOKEN_TTL_MINUTES: int = Field(default=720, ge=1, le=60 * 24 * 30)
    AUTH_REQUIRED: bool = Field(
        default=False,
        description=(
            "If true, every protected API request must carry a valid bearer token. "
            "If false (local single-user/dev mode), requests without a token are allowed, "
            "but any supplied token is still strictly validated and enforced."
        ),
    )

    @field_validator("API_V1_PREFIX")
    @classmethod
    def validate_api_prefix(cls, v: str) -> str:
        if not v.startswith("/"):
            raise ValueError("API_V1_PREFIX must start with '/'")
        return v.rstrip("/")

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        allowed_prefixes = ("postgresql://", "postgresql+psycopg://", "sqlite://")
        if not v.startswith(allowed_prefixes):
            raise ValueError(
                f"DATABASE_URL must start with one of {allowed_prefixes}, got '{v}'"
            )
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v  # type: ignore[return-value]

    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()


settings = get_settings()
