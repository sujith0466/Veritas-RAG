from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.routes.workspaces import router as workspaces_router
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db, get_workspace_settings_service
from backend.core.exceptions import get_exception_handlers
from backend.core.permissions.rbac import Role
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.services.workspace.management_service import (
    WorkspaceConflictError,
    WorkspaceNotFoundError,
    WorkspaceUnauthorizedError,
)


test_app = FastAPI()
for exc_class, handler in get_exception_handlers():
    test_app.add_exception_handler(exc_class, handler)

test_app.include_router(workspaces_router, prefix="/api/v1")


@pytest.fixture
def workspace_id():
    return uuid.uuid4()


def make_user(role: Role = Role.ADMIN) -> UserContext:
    return UserContext(
        id=uuid.uuid4(),
        email="admin@test.com",
        role=role,
        is_active=True,
        is_verified=True,
    )


def test_get_workspace_settings_success(workspace_id):
    now = datetime.now(UTC)
    mock_settings = WorkspaceSettings(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        settings_json={"general": {"retention_days": 90}},
        schema_version=1,
        version=1,
        settings_hash="abcdef123456",
        updated_at=now,
    )

    mock_service = AsyncMock()
    mock_service.get_settings.return_value = mock_settings

    user = make_user(Role.ADMIN)
    test_app.dependency_overrides[get_current_user] = lambda: user
    test_app.dependency_overrides[get_workspace_settings_service] = lambda: mock_service
    test_app.dependency_overrides[get_db] = lambda: AsyncMock()

    try:
        client = TestClient(test_app)
        res = client.get(f"/api/v1/workspaces/{workspace_id}/settings")
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["data"]["workspace_id"] == str(workspace_id)
        assert data["data"]["version"] == 1
        assert data["data"]["settings"]["general"]["retention_days"] == 90
    finally:
        test_app.dependency_overrides.clear()


def test_patch_workspace_settings_success(workspace_id):
    now = datetime.now(UTC)
    mock_settings = WorkspaceSettings(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        settings_json={"general": {"retention_days": 180}},
        schema_version=1,
        version=2,
        settings_hash="newhash123",
        updated_at=now,
    )

    mock_service = AsyncMock()
    mock_service.patch_settings.return_value = mock_settings

    user = make_user(Role.ADMIN)
    test_app.dependency_overrides[get_current_user] = lambda: user
    test_app.dependency_overrides[get_workspace_settings_service] = lambda: mock_service
    test_app.dependency_overrides[get_db] = lambda: AsyncMock()

    try:
        client = TestClient(test_app)
        res = client.patch(
            f"/api/v1/workspaces/{workspace_id}/settings",
            json={
                "expected_updated_at": now.isoformat(),
                "settings": {"general": {"retention_days": 180}},
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["data"]["version"] == 2
        assert data["data"]["settings"]["general"]["retention_days"] == 180
    finally:
        test_app.dependency_overrides.clear()


def test_patch_workspace_settings_concurrency_conflict_409(workspace_id):
    now = datetime.now(UTC)
    mock_service = AsyncMock()
    mock_service.patch_settings.side_effect = WorkspaceConflictError(
        "Settings were modified by another user. Please refresh and try again."
    )

    user = make_user(Role.ADMIN)
    test_app.dependency_overrides[get_current_user] = lambda: user
    test_app.dependency_overrides[get_workspace_settings_service] = lambda: mock_service
    test_app.dependency_overrides[get_db] = lambda: AsyncMock()

    try:
        client = TestClient(test_app)
        res = client.patch(
            f"/api/v1/workspaces/{workspace_id}/settings",
            json={
                "expected_updated_at": (now - timedelta(minutes=5)).isoformat(),
                "settings": {"general": {"retention_days": 180}},
            },
        )
        assert res.status_code == 409
        assert "Settings were modified" in str(res.json())
    finally:
        test_app.dependency_overrides.clear()


def test_patch_workspace_settings_unauthorized_403(workspace_id):
    now = datetime.now(UTC)
    mock_service = AsyncMock()
    mock_service.patch_settings.side_effect = WorkspaceUnauthorizedError(
        "Only workspace OWNER or ADMIN can modify settings."
    )

    user = make_user(Role.VIEWER)
    test_app.dependency_overrides[get_current_user] = lambda: user
    test_app.dependency_overrides[get_workspace_settings_service] = lambda: mock_service
    test_app.dependency_overrides[get_db] = lambda: AsyncMock()

    try:
        client = TestClient(test_app)
        res = client.patch(
            f"/api/v1/workspaces/{workspace_id}/settings",
            json={
                "expected_updated_at": now.isoformat(),
                "settings": {"general": {"retention_days": 180}},
            },
        )
        assert res.status_code == 403
        assert "Only workspace OWNER or ADMIN" in str(res.json())
    finally:
        test_app.dependency_overrides.clear()
