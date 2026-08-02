"""Integration tests for authentication API routes (`/api/v1/auth`).

Tests:
1. `/api/v1/auth/status` (anonymous vs authenticated).
2. `/api/v1/auth/me` (unauthenticated, expired, invalid, valid).
3. `/api/v1/health/detailed` protection (401 unauthenticated, 403 viewer, 200 admin).
"""

import time
from unittest.mock import patch
import uuid

from fastapi.testclient import TestClient
import pytest

from backend.core.auth.context import TokenPayload, UserContext
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
        user_uuid = uuid.uuid4()
        mock_user = UserContext(
            id=user_uuid,
            supabase_id=str(user_uuid),
            email="test@raguard.ai",
            role=Role.ENGINEER,
            is_active=True,
        )
        mock_payload = TokenPayload(sub=str(user_uuid), email="test@raguard.ai", role="engineer", exp=int(time.time())+3600)
        with patch(
            "backend.core.dependencies.auth.get_optional_user",
            return_value=mock_user,
        ), patch("backend.core.security.jwt.JWTService.verify_token", new_callable=__import__("unittest.mock").mock.AsyncMock, return_value=mock_payload):
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
            "backend.core.security.jwt.JWTService.verify_token",
            new_callable=__import__("unittest.mock").mock.AsyncMock,
            side_effect=InvalidTokenException("Signature verification failed"),
        ):
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer corrupted.jwt.token"},
            )
            assert response.status_code == 401
            body = response.json()
            assert body["success"] is False
            assert body["error"]["code"] == "INVALID_TOKEN"

    def test_auth_me_expired_token(self, client: TestClient) -> None:
        with patch(
            "backend.core.security.jwt.JWTService.verify_token",
            new_callable=__import__("unittest.mock").mock.AsyncMock,
            side_effect=ExpiredTokenException(),
        ):
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer expired.jwt.token"},
            )
            assert response.status_code == 401
            body = response.json()
            assert body["success"] is False
            assert body["error"]["code"] == "EXPIRED_TOKEN"

    def test_auth_me_success(self, client: TestClient) -> None:
        user_uuid = uuid.uuid4()
        mock_user = UserContext(
            id=user_uuid,
            supabase_id=str(user_uuid),
            email="admin@raguard.ai",
            role=Role.ADMIN,
            is_active=True,
        )
        mock_payload = TokenPayload(sub=str(user_uuid), email="admin@raguard.ai", role="admin", exp=int(time.time())+3600)
        with patch(
            "backend.core.dependencies.auth.get_current_user",
            return_value=mock_user,
        ), patch("backend.core.security.jwt.JWTService.verify_token", new_callable=__import__("unittest.mock").mock.AsyncMock, return_value=mock_payload):
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer valid.jwt.token"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["success"] is True
            assert body["data"]["email"] == "admin@raguard.ai"
            assert body["data"]["role"] == "admin"

    def test_detailed_health_forbidden_for_viewer(self, client: TestClient) -> None:
        user_uuid = uuid.uuid4()
        mock_user = UserContext(
            id=user_uuid,
            supabase_id=str(user_uuid),
            email="viewer@raguard.ai",
            role=Role.VIEWER,
            is_active=True,
        )
        mock_payload = TokenPayload(sub=str(user_uuid), email="viewer@raguard.ai", role="viewer", exp=int(time.time())+3600)
        with patch(
            "backend.core.dependencies.auth.get_current_user",
            return_value=mock_user,
        ), patch("backend.core.security.jwt.JWTService.verify_token", new_callable=__import__("unittest.mock").mock.AsyncMock, return_value=mock_payload):
            response = client.get(
                "/api/v1/health/detailed",
                headers={"Authorization": "Bearer viewer.token"},
            )
            assert response.status_code == 403
            body = response.json()
            assert body["success"] is False
            assert body["error"]["code"] == "AUTH_005"

    def test_detailed_health_allowed_for_admin(self, client: TestClient) -> None:
        user_uuid = uuid.uuid4()
        mock_user = UserContext(
            id=user_uuid,
            supabase_id=str(user_uuid),
            email="superadmin@raguard.ai",
            role=Role.ADMIN,
            is_active=True,
        )
        mock_payload = TokenPayload(sub=str(user_uuid), email="superadmin@raguard.ai", role="admin", exp=int(time.time())+3600)
        with patch(
            "backend.core.dependencies.auth.get_current_user",
            return_value=mock_user,
        ), patch("backend.core.security.jwt.JWTService.verify_token", new_callable=__import__("unittest.mock").mock.AsyncMock, return_value=mock_payload):
            response = client.get(
                "/api/v1/health/detailed",
                headers={"Authorization": "Bearer admin.token"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["status"] in ("healthy", "degraded", "unhealthy")
