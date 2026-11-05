"""Health and readiness check API routes."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db, validate_database_connection
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Backend Liveness Check")
def health_check() -> HealthResponse:
    """Return current operational liveness status of the Study Partner AI backend."""
    return HealthResponse(
        status="ok",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Backend Readiness Check",
)
@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Backend Readiness Check (Alias)",
)
def readiness_check(
    response: Response, db: Session = Depends(get_db)
) -> ReadinessResponse:
    """Validate database connectivity and return readiness status."""
    is_connected, detail = validate_database_connection(db)
    if not is_connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if is_connected else "degraded",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        database="connected" if is_connected else "unavailable",
        database_detail=None if is_connected else detail,
        timestamp=datetime.now(timezone.utc),
    )
