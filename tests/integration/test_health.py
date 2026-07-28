"""Integration tests for health and readiness endpoints."""

from fastapi.testclient import TestClient
import pytest


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

    def test_readiness_probe_default(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        import backend.api.v1.routes.health as health_mod

        from backend.api.v1.schemas.common import DependencyHealth
        
        async def mock_check_deps(detailed: bool = False):
            return {
                "postgresql": DependencyHealth(name="postgresql", status="healthy"),
                "redis": DependencyHealth(name="redis", status="healthy"),
                "qdrant": DependencyHealth(name="qdrant", status="healthy"),
            }

        monkeypatch.setattr(health_mod, "_check_dependencies", mock_check_deps)
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["dependencies"]["postgresql"] == "healthy"
        assert data["dependencies"]["redis"] == "healthy"
        assert data["dependencies"]["qdrant"] == "healthy"

    def test_readiness_probe_degraded_when_unhealthy(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        import backend.api.v1.routes.health as health_mod

        from backend.api.v1.schemas.common import DependencyHealth
        
        async def mock_check_deps(detailed: bool = False):
            return {
                "postgresql": DependencyHealth(name="postgresql", status="unhealthy"),
                "redis": DependencyHealth(name="redis", status="healthy"),
                "qdrant": DependencyHealth(name="qdrant", status="healthy"),
            }

        monkeypatch.setattr(health_mod, "_check_dependencies", mock_check_deps)
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"

    def test_detailed_health_requires_auth(self, client: TestClient) -> None:
        response = client.get("/api/v1/health/detailed")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_001"

    def test_detailed_health_admin(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        from unittest.mock import patch
        import uuid

        from backend.core.auth.context import UserContext
        from backend.core.permissions.rbac import Role

        mock_user = UserContext(
            id=uuid.uuid4(),
            supabase_id="sup-admin",
            email="admin@raguard.ai",
            role=Role.ADMIN,
            is_active=True,
        )
        with patch(
            "backend.services.auth.auth_service.AuthService.authenticate_token",
            return_value=mock_user,
        ):
            response = client.get(
                "/api/v1/health/detailed",
                headers={"Authorization": "Bearer valid.admin.token"},
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
