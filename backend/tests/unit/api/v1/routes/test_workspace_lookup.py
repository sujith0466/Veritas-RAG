from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
import uuid

from fastapi.testclient import TestClient
import pytest

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_workspace_provisioning_service,
    get_workspace_repository,
)
from backend.core.permissions.rbac import Role
from backend.main import create_app
from backend.models.entities.workspace import ProvisioningStatus, Workspace, WorkspaceStatus


@pytest.fixture
def test_app():
    return create_app()


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


@pytest.fixture
def mock_workspace():
    return Workspace(
        id=uuid.uuid4(),
        public_id="ACME-7X92KP",
        name="Acme Corporation",
        slug="acme-corporation",
        description="Global AI Division",
        status=WorkspaceStatus.ACTIVE.value,
        provisioning_status=ProvisioningStatus.READY.value,
        storage_prefix="workspace/mock/",
        qdrant_namespace="workspace_mock",
        updated_at=datetime.now(UTC),
    )


def test_lookup_by_public_id_success(test_app, client, mock_workspace):
    mock_repo = MagicMock()
    mock_repo.get_by_public_id = AsyncMock(return_value=mock_workspace)
    mock_repo.get_by_slug = AsyncMock(return_value=None)

def _get_error_message(response) -> str:
    body = response.json()
    if isinstance(body, dict) and "error" in body and "message" in body["error"]:
        return body["error"]["message"]
    return body.get("detail", "")


def test_lookup_by_public_id_success(test_app, client, mock_workspace):
    mock_repo = MagicMock()
    mock_repo.get_by_public_id = AsyncMock(return_value=mock_workspace)
    mock_repo.get_by_slug = AsyncMock(return_value=None)

    test_app.dependency_overrides[get_workspace_repository] = lambda: mock_repo

    response = client.get("/api/v1/workspaces/lookup", params={"identifier": "ACME-7X92KP"})
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["data"]["workspace_id"] == "ACME-7X92KP"
    assert data["data"]["workspace_name"] == "Acme Corporation"
    assert data["data"]["workspace_slug"] == "acme-corporation"
    assert data["data"]["joining_mode"] == "JOIN_CODE"
    assert data["data"]["requires_join_code"] is True
    assert data["data"]["default_join_role"] == "MEMBER"

    # Security check: tenant UUID is NOT in response
    assert str(mock_workspace.id) not in str(data)
    test_app.dependency_overrides.clear()


def test_lookup_by_slug_success(test_app, client, mock_workspace):
    mock_repo = MagicMock()
    mock_repo.get_by_public_id = AsyncMock(return_value=None)
    mock_repo.get_by_slug = AsyncMock(return_value=mock_workspace)

    test_app.dependency_overrides[get_workspace_repository] = lambda: mock_repo

    response = client.get("/api/v1/workspaces/lookup", params={"identifier": "acme-corporation"})
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["data"]["workspace_id"] == "ACME-7X92KP"
    assert data["data"]["workspace_slug"] == "acme-corporation"
    test_app.dependency_overrides.clear()


def test_lookup_rejects_tenant_uuid(test_app, client):
    test_uuid = str(uuid.uuid4())
    response = client.get("/api/v1/workspaces/lookup", params={"identifier": test_uuid})
    assert response.status_code == 400
    assert "Tenant ID (UUID) cannot be used" in _get_error_message(response)


def test_lookup_not_found(test_app, client):
    mock_repo = MagicMock()
    mock_repo.get_by_public_id = AsyncMock(return_value=None)
    mock_repo.get_by_slug = AsyncMock(return_value=None)

    test_app.dependency_overrides[get_workspace_repository] = lambda: mock_repo

    response = client.get("/api/v1/workspaces/lookup", params={"identifier": "NONEXISTENT-WS"})
    assert response.status_code == 404
    assert _get_error_message(response) == "Workspace not found."
    test_app.dependency_overrides.clear()


def test_lookup_inactive_workspace_returns_404(test_app, client, mock_workspace):
    mock_workspace.status = WorkspaceStatus.SUSPENDED.value
    mock_repo = MagicMock()
    mock_repo.get_by_public_id = AsyncMock(return_value=mock_workspace)

    test_app.dependency_overrides[get_workspace_repository] = lambda: mock_repo

    response = client.get("/api/v1/workspaces/lookup", params={"identifier": "ACME-7X92KP"})
    assert response.status_code == 404
    assert _get_error_message(response) == "Workspace not found."
    test_app.dependency_overrides.clear()


def test_create_workspace_returns_public_id(test_app, client, mock_workspace):
    mock_service = MagicMock()
    mock_service.create_workspace = AsyncMock(return_value=mock_workspace)

    def mock_user():
        return UserContext(
            id=uuid.uuid4(),
            email="owner@example.com",
            role=Role.VIEWER,
            is_active=True,
            is_verified=True,
            supabase_id="mock-supabase-id",
        )

    test_app.dependency_overrides[get_current_user] = mock_user
    test_app.dependency_overrides[get_workspace_provisioning_service] = lambda: mock_service

    response = client.post(
        "/api/v1/workspaces",
        json={"name": "Acme Corporation", "description": "Global AI Division"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["public_id"] == "ACME-7X92KP"
    assert data["data"]["slug"] == "acme-corporation"
    test_app.dependency_overrides.clear()
