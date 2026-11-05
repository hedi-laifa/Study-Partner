"""Pydantic schemas for system health and readiness check endpoints."""
from datetime import datetime
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Structured liveness health check response model."""

    status: str = Field(default="ok", description="Overall API service liveness status")
    service: str = Field(description="Application name")
    version: str = Field(description="Application version")
    environment: str = Field(description="Active runtime environment")
    timestamp: datetime = Field(description="UTC timestamp of health check")


class ReadinessResponse(BaseModel):
    """Structured readiness check response model including database status."""

    status: str = Field(description="Overall readiness status: ready or degraded")
    service: str = Field(description="Application name")
    version: str = Field(description="Application version")
    environment: str = Field(description="Active runtime environment")
    database: str = Field(description="Database connection status: connected or unavailable")
    database_detail: str | None = Field(default=None, description="Diagnostic detail if degraded")
    timestamp: datetime = Field(description="UTC timestamp of readiness check")
