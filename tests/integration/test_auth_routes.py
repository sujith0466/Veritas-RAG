"""Integration tests for authentication API routes (`/api/v1/auth`).

Tests:
1. `/api/v1/auth/status` (anonymous vs authenticated).
2. `/api/v1/auth/me` (unauthenticated, expired, invalid, valid).
3. `/api/v1/health/detailed` protection (401 unauthenticated, 403 viewer, 200 admin).
"""

from unittest.mock import patch
import uuid

from fastapi.testclient import TestClient
import pytest

from backend.core.auth.context import UserContext
from backend.core.exceptions.auth import ExpiredTokenException, InvalidTokenException
from backend.core.permissions.rbac import Role


@pytest.mark.integration
class TestAuthRoutes:
    def test_auth_status_anonymous(self, client: TestClient) -> None:
        response = client.get("/api/v1/auth/status")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["is_authenticated"] is False
        assert body["data"]["user"] is None
        assert "X-Correlation-ID" in response.headers

    def test_auth_status_authenticated(self, client: TestClient) -> None:
        mock_user = UserContext(
            id=uuid.uuid4(),
            supabase_id="sup-123",
            email="test@raguard.ai",
            role=Role.ENGINEER,
            is_active=True,
        )
        with patch(
            "backend.services.auth.auth_service.AuthService.authenticate_token",
            return_value=mock_user,
        ):
            response = client.get(
                "/api/v1/auth/status",
                headers={"Authorization": "Bearer valid.token.here"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["success"] is True
            assert body["data"]["is_authenticated"] is True
            assert body["data"]["user"]["email"] == "test@raguard.ai"
            assert body["data"]["user"]["role"] == "engineer"

    def test_auth_me_unauthenticated(self, client: TestClient) -> None:
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401
        body = response.json()
        assert body["success"] is False
        assert body["error"]["code"] == "AUTH_001"
        assert "Authentication required" in body["error"]["message"]

    def test_auth_me_invalid_token(self, client: TestClient) -> None:
        with patch(
            "backend.services.auth.auth_service.AuthService.authenticate_token",
            side_effect=InvalidTokenException("Signature verification failed"),
        ):
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer corrupted.jwt.token"},
            )
            assert response.status_code == 401
            body = response.json()
            assert body["success"] is False
            assert body["error"]["code"] == "AUTH_002"

    def test_auth_me_expired_token(self, client: TestClient) -> None:
        with patch(
            "backend.services.auth.auth_service.AuthService.authenticate_token",
            side_effect=ExpiredTokenException(),
        ):
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer expired.jwt.token"},
            )
            assert response.status_code == 401
            body = response.json()
            assert body["success"] is False
            assert body["error"]["code"] == "AUTH_003"

    def test_auth_me_success(self, client: TestClient) -> None:
        mock_user = UserContext(
            id=uuid.uuid4(),
            supabase_id="sup-456",
            email="admin@raguard.ai",
            role=Role.ADMIN,
            is_active=True,
        )
        with patch(
            "backend.services.auth.auth_service.AuthService.authenticate_token",
            return_value=mock_user,
        ):
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer valid.admin.token"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["success"] is True
            assert body["data"]["email"] == "admin@raguard.ai"
            assert body["data"]["role"] == "admin"

    def test_detailed_health_forbidden_for_viewer(self, client: TestClient) -> None:
        mock_user = UserContext(
            id=uuid.uuid4(),
            supabase_id="sup-789",
            email="viewer@raguard.ai",
            role=Role.VIEWER,
            is_active=True,
        )
        with patch(
            "backend.services.auth.auth_service.AuthService.authenticate_token",
            return_value=mock_user,
        ):
            response = client.get(
                "/api/v1/health/detailed",
                headers={"Authorization": "Bearer viewer.token"},
            )
            assert response.status_code == 403
            body = response.json()
            assert body["success"] is False
            assert body["error"]["code"] == "AUTH_005"

    def test_detailed_health_allowed_for_admin(self, client: TestClient) -> None:
        mock_user = UserContext(
            id=uuid.uuid4(),
            supabase_id="sup-admin",
            email="superadmin@raguard.ai",
            role=Role.ADMIN,
            is_active=True,
        )
        with patch(
            "backend.services.auth.auth_service.AuthService.authenticate_token",
            return_value=mock_user,
        ):
            response = client.get(
                "/api/v1/health/detailed",
                headers={"Authorization": "Bearer admin.token"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["status"] in ("healthy", "degraded", "unhealthy")
