"""Unit tests for Workspace Join Code API Routes (WS-A3).

Validates:
- GET /api/v1/workspaces/{workspace_id}/join-code
- PATCH /api/v1/workspaces/{workspace_id}/join-code/settings
- POST /api/v1/workspaces/{workspace_id}/join-code/generate
- POST /api/v1/workspaces/{workspace_id}/join-code/regenerate
- Verification check (403 if unverified)
- RBAC check (403 if unauthorized)
- 400 validation on invalid payload
- 200 responses with exact contract schema
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
import uuid

from fastapi.testclient import TestClient
import pytest

from backend.api.v1.schemas.workspace_onboarding import (
    JoinCodeGenerateResponse,
    JoinCodeSettingsSchema,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db, get_join_code_service
from backend.core.permissions.rbac import Role
from backend.main import create_app
from backend.services.workspace.management_service import (
    WorkspaceNotFoundError,
    WorkspaceUnauthorizedError,
)


@pytest.fixture
def test_app():
    return create_app()


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


@pytest.fixture
def verified_admin_user():
    return UserContext(
        id=uuid.uuid4(),
        email="admin@example.com",
        role=Role.MEMBER,
        workspace_id=uuid.uuid4(),
        is_verified=True,
    )


@pytest.fixture
def unverified_user():
    return UserContext(
        id=uuid.uuid4(),
        email="unverified@example.com",
        role=Role.MEMBER,
        workspace_id=uuid.uuid4(),
        is_verified=False,
    )


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    return session


@pytest.fixture
def mock_join_service():
    service = AsyncMock()
    return service


def test_get_join_code_unverified_forbidden(test_app, client, unverified_user, mock_db_session, mock_join_service):
    workspace_id = uuid.uuid4()
    test_app.dependency_overrides[get_current_user] = lambda: unverified_user
    test_app.dependency_overrides[get_db] = lambda: mock_db_session
    test_app.dependency_overrides[get_join_code_service] = lambda: mock_join_service

    try:
        response = client.get(f"/api/v1/workspaces/{workspace_id}/join-code")
        assert response.status_code == 403
    finally:
        test_app.dependency_overrides.clear()


def test_get_join_code_success(test_app, client, verified_admin_user, mock_db_session, mock_join_service):
    workspace_id = uuid.uuid4()
    mock_join_service.get_join_code_settings = AsyncMock(
        return_value=JoinCodeSettingsSchema(
            enabled=True,
            default_role="MEMBER",
            require_approval=False,
            expires_at=None,
            generated_at=datetime.now(UTC),
            generated_by=verified_admin_user.id,
            has_code=True,
            max_uses=10,
            current_uses=2,
        )
    )

    test_app.dependency_overrides[get_current_user] = lambda: verified_admin_user
    test_app.dependency_overrides[get_db] = lambda: mock_db_session
    test_app.dependency_overrides[get_join_code_service] = lambda: mock_join_service

    try:
        response = client.get(f"/api/v1/workspaces/{workspace_id}/join-code")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["default_role"] == "MEMBER"
        assert data["has_code"] is True
        assert data["max_uses"] == 10
        assert data["current_uses"] == 2
        # Ensure hash/code NEVER present in response
        assert "code_hash" not in data
        assert "join_code" not in data
    finally:
        test_app.dependency_overrides.clear()


def test_get_join_code_unauthorized(test_app, client, verified_admin_user, mock_db_session, mock_join_service):
    workspace_id = uuid.uuid4()
    mock_join_service.get_join_code_settings = AsyncMock(
        side_effect=WorkspaceUnauthorizedError("Only workspace OWNER or ADMIN can manage join code settings.")
    )

    test_app.dependency_overrides[get_current_user] = lambda: verified_admin_user
    test_app.dependency_overrides[get_db] = lambda: mock_db_session
    test_app.dependency_overrides[get_join_code_service] = lambda: mock_join_service

    try:
        response = client.get(f"/api/v1/workspaces/{workspace_id}/join-code")
        assert response.status_code == 403
    finally:
        test_app.dependency_overrides.clear()


def test_patch_join_code_settings_success(test_app, client, verified_admin_user, mock_db_session, mock_join_service):
    workspace_id = uuid.uuid4()
    mock_join_service.patch_join_code_settings = AsyncMock(
        return_value=JoinCodeSettingsSchema(
            enabled=False,
            default_role="VIEWER",
            require_approval=True,
            expires_at=None,
            generated_at=None,
            generated_by=None,
            has_code=False,
            max_uses=20,
            current_uses=0,
        )
    )

    test_app.dependency_overrides[get_current_user] = lambda: verified_admin_user
    test_app.dependency_overrides[get_db] = lambda: mock_db_session
    test_app.dependency_overrides[get_join_code_service] = lambda: mock_join_service

    try:
        response = client.patch(
            f"/api/v1/workspaces/{workspace_id}/join-code/settings",
            json={"enabled": False, "default_role": "VIEWER", "require_approval": True, "max_uses": 20},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["default_role"] == "VIEWER"
        assert data["max_uses"] == 20
    finally:
        test_app.dependency_overrides.clear()


def test_generate_join_code_success(test_app, client, verified_admin_user, mock_db_session, mock_join_service):
    workspace_id = uuid.uuid4()
    mock_join_service.generate_new_join_code = AsyncMock(
        return_value=JoinCodeGenerateResponse(
            success=True,
            join_code="VR-2NH58X",
            expires_at=datetime.now(UTC),
            default_role="MEMBER",
            warning="Cryptographic hash stored only.",
        )
    )

    test_app.dependency_overrides[get_current_user] = lambda: verified_admin_user
    test_app.dependency_overrides[get_db] = lambda: mock_db_session
    test_app.dependency_overrides[get_join_code_service] = lambda: mock_join_service

    try:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/join-code/generate",
            params={"expires_in_days": 30, "default_role": "MEMBER", "max_uses": 50},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["join_code"] == "VR-2NH58X"
        assert data["default_role"] == "MEMBER"
        assert "warning" in data
    finally:
        test_app.dependency_overrides.clear()


def test_regenerate_join_code_success(test_app, client, verified_admin_user, mock_db_session, mock_join_service):
    workspace_id = uuid.uuid4()
    mock_join_service.generate_new_join_code = AsyncMock(
        return_value=JoinCodeGenerateResponse(
            success=True,
            join_code="VR-8TKP9M",
            expires_at=datetime.now(UTC),
            default_role="MEMBER",
            warning="Cryptographic hash stored only.",
        )
    )

    test_app.dependency_overrides[get_current_user] = lambda: verified_admin_user
    test_app.dependency_overrides[get_db] = lambda: mock_db_session
    test_app.dependency_overrides[get_join_code_service] = lambda: mock_join_service

    try:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/join-code/regenerate",
            params={"expires_in_days": 15, "max_uses": 25},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["join_code"] == "VR-8TKP9M"
    finally:
        test_app.dependency_overrides.clear()


def test_generate_join_code_invalid_role(test_app, client, verified_admin_user, mock_db_session, mock_join_service):
    workspace_id = uuid.uuid4()
    mock_join_service.generate_new_join_code = AsyncMock(
        side_effect=ValueError("Default role must be 'MEMBER' or 'VIEWER', got 'OWNER'.")
    )

    test_app.dependency_overrides[get_current_user] = lambda: verified_admin_user
    test_app.dependency_overrides[get_db] = lambda: mock_db_session
    test_app.dependency_overrides[get_join_code_service] = lambda: mock_join_service

    try:
        response = client.post(
            f"/api/v1/workspaces/{workspace_id}/join-code/generate",
            params={"default_role": "OWNER"},
        )
        assert response.status_code == 400
    finally:
        test_app.dependency_overrides.clear()
