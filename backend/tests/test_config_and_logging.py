"""Tests for configuration validation and structured JSON logging."""
import json
import logging

from pydantic import ValidationError
import pytest

from app.core.config import Settings
from app.core.logging import StructuredJsonFormatter


def test_valid_settings_configuration() -> None:
    """Verify valid environment settings pass Pydantic validation."""
    cfg = Settings(
        APP_NAME="Study Partner AI",
        APP_ENV="testing",
        BACKEND_PORT=8000,
        API_V1_PREFIX="/api/v1/",
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/testdb",
        CORS_ORIGINS="http://localhost:5173, http://127.0.0.1:5173",  # type: ignore[arg-type]
    )
    assert cfg.API_V1_PREFIX == "/api/v1"
    assert cfg.CORS_ORIGINS == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_invalid_database_url_rejected() -> None:
    """Verify unsupported DATABASE_URL schemes raise a ValidationError."""
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="mysql://user:pass@localhost:3306/db")


def test_invalid_api_prefix_rejected() -> None:
    """Verify API_V1_PREFIX without leading slash raises a ValidationError."""
    with pytest.raises(ValidationError):
        Settings(API_V1_PREFIX="api/v1")


def test_structured_json_formatter() -> None:
    """Verify StructuredJsonFormatter emits valid JSON with expected fields."""
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="study_partner",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="Test structured log entry",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-123"
    record.path = "/api/v1/health"
    record.method = "GET"
    record.status_code = 200

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "study_partner"
    assert parsed["message"] == "Test structured log entry"
    assert parsed["request_id"] == "req-123"
    assert parsed["path"] == "/api/v1/health"
    assert parsed["status_code"] == 200
    assert "timestamp" in parsed
