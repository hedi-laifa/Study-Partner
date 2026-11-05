"""Tests for backend root, liveness health, and database readiness endpoints."""
from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient) -> None:
    """Verify root endpoint returns service metadata and endpoint links."""
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "Study Partner AI"
    assert payload["health"] == "/api/v1/health"
    assert payload["ready"] == "/api/v1/health/ready"
    assert "X-Request-ID" in response.headers


def test_health_check_endpoint(client: TestClient) -> None:
    """Verify GET /api/v1/health returns status ok and structured metadata."""
    from app.core.config import settings

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "Study Partner AI"
    assert payload["version"] == settings.APP_VERSION
    assert "timestamp" in payload


def test_readiness_check_endpoint(client: TestClient) -> None:
    """Verify GET /api/v1/health/ready and /api/v1/ready validate database connection."""
    for path in ("/api/v1/health/ready", "/api/v1/ready"):
        response = client.get(path)
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ready"
        assert payload["database"] == "connected"
        assert payload["database_detail"] is None
