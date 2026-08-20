"""Unit tests for health probes (Liveness, Readiness, Startup, and Detailed Health)."""

import time
from unittest.mock import AsyncMock, patch
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import backend.api.v1.routes.health as health_mod
from backend.api.v1.schemas.common import DependencyHealth
from backend.core.auth.context import TokenPayload, UserContext
from backend.core.permissions.rbac import Role


@pytest.fixture(autouse=True)
def clean_startup_state():
    """Ensure startup state is reset before and after each test."""
    health_mod.reset_startup_state()
    yield
    health_mod.reset_startup_state()


from backend.core.exceptions.handlers import get_exception_handlers


@pytest.fixture
def client():
    """Create lightweight test client with health router and exception handlers."""
    test_app = FastAPI()
    for exc_class, handler in get_exception_handlers():
        test_app.add_exception_handler(exc_class, handler)
    test_app.include_router(health_mod.router)
    test_app.include_router(health_mod.router, prefix="/api/v1")
    return TestClient(test_app)


class TestHealthProbes:
    """Test suite for F14.6 Health Probes."""

    def test_overall_health(self, client: TestClient) -> None:
        """Verify /health and /api/v1/health return general health status."""
        for path in ("/health", "/api/v1/health"):
            response = client.get(path)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "version" in data
            assert "environment" in data

    def test_liveness_probe(self, client: TestClient) -> None:
        """Verify /health/live returns 200, uptime, and timestamp."""
        for path in ("/health/live", "/api/v1/health/live"):
            response = client.get(path)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "alive"
            assert isinstance(data["uptime_seconds"], (int, float))
            assert data["uptime_seconds"] >= 0
            assert "timestamp" in data

    def test_startup_probe_lifecycle(self, client: TestClient) -> None:
        """Verify /health/startup returns 503 before startup and 200 after startup."""
        for path in ("/health/startup", "/api/v1/health/startup"):
            # Initial state: startup not complete
            health_mod.reset_startup_state()
            response = client.get(path)
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "starting"
            assert "timestamp" in data

            # Mark startup complete
            health_mod.mark_startup_complete()
            response = client.get(path)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "started"
            assert "timestamp" in data

    def test_readiness_probe_all_healthy(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify readiness returns 200 when all required dependencies are healthy."""
        async def mock_check_deps(detailed: bool = False):
            return {
                "postgresql": DependencyHealth(name="postgresql", status="healthy"),
                "redis": DependencyHealth(name="redis", status="healthy"),
                "qdrant": DependencyHealth(name="qdrant", status="healthy"),
                "object_storage": DependencyHealth(name="object_storage", status="healthy"),
                "llm_provider": DependencyHealth(name="llm_provider", status="healthy"),
            }

        monkeypatch.setattr(health_mod, "_check_dependencies", mock_check_deps)

        for path in ("/health/ready", "/api/v1/health/ready"):
            response = client.get(path)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"
            assert data["dependencies"]["postgresql"] == "healthy"
            assert data["dependencies"]["redis"] == "healthy"
            assert data["dependencies"]["qdrant"] == "healthy"
            assert data["dependencies"]["object_storage"] == "healthy"

    def test_readiness_probe_qdrant_unhealthy(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify readiness returns 503 when Qdrant vector DB is unhealthy."""
        async def mock_check_deps(detailed: bool = False):
            return {
                "postgresql": DependencyHealth(name="postgresql", status="healthy"),
                "redis": DependencyHealth(name="redis", status="healthy"),
                "qdrant": DependencyHealth(
                    name="qdrant", status="unhealthy", error="Connection refused to 127.0.0.1:6333"
                ),
                "object_storage": DependencyHealth(name="object_storage", status="healthy"),
                "llm_provider": DependencyHealth(name="llm_provider", status="healthy"),
            }

        monkeypatch.setattr(health_mod, "_check_dependencies", mock_check_deps)

        for path in ("/health/ready", "/api/v1/health/ready"):
            response = client.get(path)
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"
            assert data["dependencies"]["qdrant"] == "unhealthy"

    def test_readiness_probe_postgres_unhealthy(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify readiness returns 503 when PostgreSQL is unhealthy."""
        async def mock_check_deps(detailed: bool = False):
            return {
                "postgresql": DependencyHealth(name="postgresql", status="unhealthy"),
                "redis": DependencyHealth(name="redis", status="healthy"),
                "qdrant": DependencyHealth(name="qdrant", status="healthy"),
                "object_storage": DependencyHealth(name="object_storage", status="healthy"),
            }

        monkeypatch.setattr(health_mod, "_check_dependencies", mock_check_deps)

        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"

    def test_readiness_probe_redis_unhealthy(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify readiness returns 503 when Redis is unhealthy."""
        async def mock_check_deps(detailed: bool = False):
            return {
                "postgresql": DependencyHealth(name="postgresql", status="healthy"),
                "redis": DependencyHealth(name="redis", status="unhealthy"),
                "qdrant": DependencyHealth(name="qdrant", status="healthy"),
                "object_storage": DependencyHealth(name="object_storage", status="healthy"),
            }

        monkeypatch.setattr(health_mod, "_check_dependencies", mock_check_deps)

        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"

    def test_readiness_probe_no_information_disclosure(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify readiness response never leaks internal error messages or credentials."""
        async def mock_check_deps(detailed: bool = False):
            return {
                "postgresql": DependencyHealth(
                    name="postgresql",
                    status="unhealthy",
                    error="FATAL: password authentication failed for user raguard at 10.0.0.5:5432",
                ),
                "redis": DependencyHealth(
                    name="redis",
                    status="healthy",
                ),
                "qdrant": DependencyHealth(
                    name="qdrant",
                    status="healthy",
                ),
                "object_storage": DependencyHealth(
                    name="object_storage",
                    status="healthy",
                ),
            }

        monkeypatch.setattr(health_mod, "_check_dependencies", mock_check_deps)

        response = client.get("/health/ready")
        assert response.status_code == 503
        body_str = response.text
        # Assert sensitive strings are not present in unauthenticated response
        assert "password" not in body_str
        assert "10.0.0.5" not in body_str
        assert "authentication failed" not in body_str
        # Verify structure only maps dependency names to simple status string
        data = response.json()
        assert data["dependencies"]["postgresql"] == "unhealthy"
        assert isinstance(data["dependencies"]["postgresql"], str)

    def test_detailed_health_requires_auth(self, client: TestClient) -> None:
        """Verify /health/detailed returns 401 when unauthenticated."""
        response = client.get("/health/detailed")
        assert response.status_code == 401

    def test_detailed_health_platform_admin(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify /health/detailed returns 200 with dependency list for PLATFORM_ADMIN."""
        async def mock_check_deps(detailed: bool = False):
            return {
                "postgresql": DependencyHealth(name="postgresql", status="healthy", latency_ms=1.2),
                "redis": DependencyHealth(name="redis", status="healthy", latency_ms=0.8),
                "qdrant": DependencyHealth(name="qdrant", status="healthy", latency_ms=2.1),
                "object_storage": DependencyHealth(name="object_storage", status="healthy", latency_ms=4.0),
                "llm_provider": DependencyHealth(name="llm_provider", status="healthy", latency_ms=50.0),
            }

        monkeypatch.setattr(health_mod, "_check_dependencies", mock_check_deps)

        user_uuid = uuid.uuid4()
        mock_user = UserContext(
            id=user_uuid,
            supabase_id=str(user_uuid),
            email="admin@raguard.ai",
            role=Role.PLATFORM_ADMIN,
            is_active=True,
        )
        mock_payload = TokenPayload(
            sub=str(user_uuid),
            email="admin@raguard.ai",
            role="platform_admin",
            exp=int(time.time()) + 3600,
        )

        from backend.core.dependencies.auth import get_current_user

        client.app.dependency_overrides[get_current_user] = lambda: mock_user
        try:
            response = client.get(
                "/health/detailed",
                headers={"Authorization": "Bearer test-admin-token"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ("healthy", "degraded", "unhealthy")
            assert "dependencies" in data
            assert len(data["dependencies"]) == 5
        finally:
            client.app.dependency_overrides.clear()
