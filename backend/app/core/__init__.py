"""Core configuration, logging, and exception handling module."""
from app.core.config import Settings, get_settings, settings
from app.core.exceptions import (
    AppException,
    ConflictError,
    DatabaseUnavailableError,
    EntityNotFoundError,
    OwnershipViolationError,
    register_exception_handlers,
)
from app.core.logging import configure_logging, logger

__all__ = [
    "AppException",
    "ConflictError",
    "DatabaseUnavailableError",
    "EntityNotFoundError",
    "OwnershipViolationError",
    "Settings",
    "configure_logging",
    "get_settings",
    "logger",
    "register_exception_handlers",
    "settings",
]
