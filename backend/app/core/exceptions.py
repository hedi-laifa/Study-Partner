"""Application exceptions and FastAPI error handlers."""
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.logging import logger


class AppException(Exception):
    """Base domain exception for Study Partner AI."""

    def __init__(
        self,
        detail: str,
        error_code: str = "APPLICATION_ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.error_code = error_code
        self.status_code = status_code
        self.extra = extra or {}


class EntityNotFoundError(AppException):
    """Raised when a requested resource does not exist."""

    def __init__(self, entity: str, identifier: Any) -> None:
        super().__init__(
            detail=f"{entity} with id '{identifier}' was not found.",
            error_code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class OwnershipViolationError(AppException):
    """Raised when a user attempts to access or modify another user's resource."""

    def __init__(self, detail: str = "You do not have permission to access this resource.") -> None:
        super().__init__(
            detail=detail,
            error_code="FORBIDDEN_OWNERSHIP_VIOLATION",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ConflictError(AppException):
    """Raised when an operation violates a uniqueness or state constraint."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            detail=detail,
            error_code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
        )


class DatabaseUnavailableError(AppException):
    """Raised when the database connection cannot be established."""

    def __init__(self, detail: str = "Database is currently unavailable.") -> None:
        super().__init__(
            detail=detail,
            error_code="DATABASE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class VectorStoreUnavailableError(AppException):
    """Raised when ChromaDB vector store is unavailable or fails."""

    def __init__(self, detail: str = "Vector store is currently unavailable.") -> None:
        super().__init__(
            detail=detail,
            error_code="VECTOR_STORE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register unified JSON exception handlers on the FastAPI application."""

    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            exc.detail,
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": exc.status_code,
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": exc.error_code,
                **({"extra": exc.extra} if exc.extra else {}),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "Request payload validation failed",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": 422,
            },
        )
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Request validation failed.",
                "error_code": "VALIDATION_ERROR",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.error(
            f"Database integrity error: {exc}",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": status.HTTP_409_CONFLICT,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Resource conflict or constraint violation.",
                "error_code": "DATABASE_INTEGRITY_ERROR",
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_sqlalchemy_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error(
            f"Database error: {exc}",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An unexpected database error occurred.",
                "error_code": "DATABASE_ERROR",
            },
        )
