from unittest.mock import AsyncMock, MagicMock
import uuid

from fastapi.testclient import TestClient

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_workspace_provisioning_service
from backend.core.permissions.rbac import Role
from backend.main import create_app
from backend.models.entities.workspace import ProvisioningStatus, Workspace, WorkspaceStatus

app = create_app()

def get_mock_verified_user():
    return UserContext(
        id=uuid.uuid4(),
        email="test@example.com",
        role=Role.VIEWER,
        is_active=True,
        is_verified=True,
        supabase_id="mock-supabase-id",
    )

def get_mock_unverified_user():
    return UserContext(
        id=uuid.uuid4(),
        email="unverified@example.com",
        role=Role.VIEWER,
        is_active=True,
        is_verified=False,
        supabase_id="mock-supabase-id",
    )


from datetime import UTC, datetime


def test_create_workspace_success():
    mock_service = MagicMock()
    mock_ws = Workspace(
        id=uuid.uuid4(),
        name="Integration Corp",
        slug="integration-corp",
        description="Testing create",
        status=WorkspaceStatus.ACTIVE.value,
        provisioning_status=ProvisioningStatus.READY.value,
        updated_at=datetime.now(UTC),
    )
    mock_service.create_workspace = AsyncMock(return_value=mock_ws)

    app.dependency_overrides[get_current_user] = get_mock_verified_user
    app.dependency_overrides[get_workspace_provisioning_service] = lambda: mock_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/workspaces",
        json={"name": "Integration Corp", "description": "Testing create"}
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Integration Corp"
    assert data["data"]["slug"] == "integration-corp"
    assert data["data"]["status"] == "ACTIVE"
    assert data["data"]["provisioning_status"] == "READY"


def test_create_workspace_unverified():
    app.dependency_overrides[get_current_user] = get_mock_unverified_user
    client = TestClient(app)

    response = client.post(
        "/api/v1/workspaces",
        json={"name": "Unverified Corp"}
    )

    app.dependency_overrides.clear()

    assert response.status_code == 403
    err_body = response.json()
    msg = err_body.get("error", {}).get("message", "") or err_body.get("detail", "")
    assert "Email verification required" in msg

