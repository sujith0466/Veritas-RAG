"""Integration tests for health, readiness, and startup endpoints."""

from fastapi.testclient import TestClient
import pytest

import backend.api.v1.routes.health as health_mod
from backend.api.v1.schemas.common import DependencyHealth


@pytest.fixture(autouse=True)
def clean_startup_state():
    """Ensure startup state is reset before and after each test."""
    health_mod.reset_startup_state()
    yield
    health_mod.reset_startup_state()


@pytest.mark.integration
class TestHealthEndpoints:
    def test_overall_health(self, client: TestClient) -> None:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data
        assert "timestamp" in data

    def test_liveness_probe(self, client: TestClient) -> None:
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0

    def test_startup_probe(self, client: TestClient) -> None:
        health_mod.reset_startup_state()
        res_starting = client.get("/api/v1/health/startup")
        assert res_starting.status_code == 503
        assert res_starting.json()["status"] == "starting"

        health_mod.mark_startup_complete()
        res_started = client.get("/api/v1/health/startup")
        assert res_started.status_code == 200
        assert res_started.json()["status"] == "started"

    def test_readiness_probe_default(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        async def mock_check_deps(detailed: bool = False):
            return {
                "postgresql": DependencyHealth(name="postgresql", status="healthy"),
                "redis": DependencyHealth(name="redis", status="healthy"),
                "qdrant": DependencyHealth(name="qdrant", status="healthy"),
                "object_storage": DependencyHealth(name="object_storage", status="healthy"),
            }

        monkeypatch.setattr(health_mod, "_check_dependencies", mock_check_deps)
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["dependencies"]["postgresql"] == "healthy"
        assert data["dependencies"]["redis"] == "healthy"
        assert data["dependencies"]["qdrant"] == "healthy"
        assert data["dependencies"]["object_storage"] == "healthy"

    def test_readiness_probe_degraded_when_unhealthy(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        async def mock_check_deps(detailed: bool = False):
            return {
                "postgresql": DependencyHealth(name="postgresql", status="unhealthy"),
                "redis": DependencyHealth(name="redis", status="healthy"),
                "qdrant": DependencyHealth(name="qdrant", status="healthy"),
                "object_storage": DependencyHealth(name="object_storage", status="healthy"),
            }

        monkeypatch.setattr(health_mod, "_check_dependencies", mock_check_deps)
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"

    def test_readiness_probe_degraded_when_qdrant_unhealthy(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        async def mock_check_deps(detailed: bool = False):
            return {
                "postgresql": DependencyHealth(name="postgresql", status="healthy"),
                "redis": DependencyHealth(name="redis", status="healthy"),
                "qdrant": DependencyHealth(name="qdrant", status="unhealthy"),
                "object_storage": DependencyHealth(name="object_storage", status="healthy"),
            }

        monkeypatch.setattr(health_mod, "_check_dependencies", mock_check_deps)
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"
        assert response.json()["dependencies"]["qdrant"] == "unhealthy"

    def test_detailed_health_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/v1/health/detailed")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_001"

    def test_detailed_health_admin(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import patch
        import uuid

        from backend.core.auth.context import TokenPayload, UserContext
        from backend.core.permissions.rbac import Role

        async def mock_check_deps(detailed: bool = False):
            return {
                "postgresql": DependencyHealth(name="postgresql", status="healthy", latency_ms=1.5),
                "redis": DependencyHealth(name="redis", status="healthy", latency_ms=0.8),
                "qdrant": DependencyHealth(name="qdrant", status="healthy", latency_ms=2.0),
                "object_storage": DependencyHealth(name="object_storage", status="healthy", latency_ms=3.5),
                "llm_provider": DependencyHealth(name="llm_provider", status="healthy", latency_ms=45.0),
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
            exp=int(__import__("time").time()) + 3600,
        )

        with patch(
            "backend.core.dependencies.auth.get_current_user",
            return_value=mock_user,
        ), patch(
            "backend.core.security.jwt.JWTService.verify_token",
            new_callable=__import__("unittest.mock").mock.AsyncMock,
            return_value=mock_payload,
        ):
            response = client.get(
                "/api/v1/health/detailed",
                headers={"Authorization": "Bearer admin.token"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ("healthy", "degraded", "unhealthy")
            assert len(data["dependencies"]) >= 3
            names = [d["name"] for d in data["dependencies"]]
            assert "postgresql" in names
            assert "redis" in names
            assert "qdrant" in names
            assert "llm_provider" in names
