"""Integration tests for F4.1 Workspace Invitation API routes."""

import datetime
from datetime import UTC
from unittest.mock import AsyncMock
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.api.v1.routes.workspace_invitations import (
    invitations_router,
    workspace_invitations_router,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_db,
    get_workspace_invitation_service,
)
from backend.core.permissions.rbac import Role
from backend.models.entities.workspace_invitation import (
    InvitationStatus,
    WorkspaceInvitation,
)
from backend.services.workspace.invitation_service import (
    InvitationConflictError,
    InvitationRateLimitError,
)

# Set up test FastAPI app
app = FastAPI()
app.include_router(workspace_invitations_router, prefix="/api/v1")
app.include_router(invitations_router, prefix="/api/v1")


def get_mock_admin_user() -> UserContext:
    return UserContext(
        id=uuid.uuid4(),
        email="admin@raguard.ai",
        role=Role.ADMIN,
        is_active=True,
        is_verified=True,
        supabase_id="mock-admin-supabase-id",
        session_id=uuid.uuid4(),
    )


@pytest.fixture
def mock_invitation_service():
    return AsyncMock()


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def client(mock_invitation_service, mock_db_session):
    app.dependency_overrides[get_current_user] = get_mock_admin_user
    app.dependency_overrides[get_db] = lambda: mock_db_session
    app.dependency_overrides[get_workspace_invitation_service] = lambda: mock_invitation_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_send_invitation_api_success(client, mock_invitation_service):
    workspace_id = uuid.uuid4()
    invitation_id = uuid.uuid4()
    now_utc = datetime.datetime.now(UTC)

    mock_inv = WorkspaceInvitation(
        id=invitation_id,
        workspace_id=workspace_id,
        email="newuser@example.com",
        role="MEMBER",
        token_hash="testhash123",
        status=InvitationStatus.PENDING.value,
        expires_at=now_utc + datetime.timedelta(days=7),
        resend_count=0,
        version=1,
        created_at=now_utc,
        updated_at=now_utc,
    )
    mock_invitation_service.send_invitation.return_value = mock_inv

    payload = {
        "email": "newuser@example.com",
        "role": "MEMBER",
        "custom_message": "Join us on RAGuard!",
    }
    response = client.post(f"/api/v1/workspaces/{workspace_id}/invitations", json=payload)

    assert response.status_code == 201
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["data"]["email"] == "newuser@example.com"
    assert json_data["data"]["role"] == "MEMBER"
    assert json_data["data"]["status"] == "PENDING"
    assert "token_hash" not in json_data["data"]  # Ensure hash is never exposed


def test_send_invitation_api_conflict_409(client, mock_invitation_service):
    workspace_id = uuid.uuid4()
    mock_invitation_service.send_invitation.side_effect = InvitationConflictError(
        "A pending invitation already exists for this email in this workspace."
    )

    payload = {"email": "duplicate@example.com", "role": "MEMBER"}
    response = client.post(f"/api/v1/workspaces/{workspace_id}/invitations", json=payload)

    assert response.status_code == 409
    assert "A pending invitation already exists" in response.json()["detail"]


def test_send_invitation_api_rate_limit_429(client, mock_invitation_service):
    workspace_id = uuid.uuid4()
    mock_invitation_service.send_invitation.side_effect = InvitationRateLimitError(
        "Workspace invitation rate limit exceeded."
    )

    payload = {"email": "spammed@example.com", "role": "MEMBER"}
    response = client.post(f"/api/v1/workspaces/{workspace_id}/invitations", json=payload)

    assert response.status_code == 429
    assert "rate limit exceeded" in response.json()["detail"]


def test_list_invitations_api_success(client, mock_invitation_service):
    workspace_id = uuid.uuid4()
    now_utc = datetime.datetime.now(UTC)

    mock_inv = WorkspaceInvitation(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        email="user1@example.com",
        role="MEMBER",
        token_hash="hash1",
        status=InvitationStatus.PENDING.value,
        expires_at=now_utc + datetime.timedelta(days=7),
        resend_count=0,
        version=1,
        created_at=now_utc,
        updated_at=now_utc,
    )
    mock_invitation_service.list_invitations.return_value = ([mock_inv], 1)

    response = client.get(f"/api/v1/workspaces/{workspace_id}/invitations?page=1&page_size=20")

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["total"] == 1
    assert len(json_data["items"]) == 1
    assert json_data["items"][0]["email"] == "user1@example.com"


def test_resend_invitation_api_success(client, mock_invitation_service):
    workspace_id = uuid.uuid4()
    invitation_id = uuid.uuid4()
    now_utc = datetime.datetime.now(UTC)

    mock_inv = WorkspaceInvitation(
        id=invitation_id,
        workspace_id=workspace_id,
        email="resend@example.com",
        role="MEMBER",
        token_hash="newhash",
        status=InvitationStatus.PENDING.value,
        expires_at=now_utc + datetime.timedelta(days=7),
        resend_count=1,
        last_resent_at=now_utc,
        version=2,
        created_at=now_utc,
        updated_at=now_utc,
    )
    mock_invitation_service.resend_invitation.return_value = mock_inv

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/invitations/{invitation_id}/resend",
        json={"custom_message": "Gentle reminder to join!"},
    )

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["resend_count"] == 1


def test_revoke_invitation_api_success(client, mock_invitation_service):
    workspace_id = uuid.uuid4()
    invitation_id = uuid.uuid4()
    now_utc = datetime.datetime.now(UTC)

    mock_inv = WorkspaceInvitation(
        id=invitation_id,
        workspace_id=workspace_id,
        email="revoke@example.com",
        role="MEMBER",
        token_hash="hash",
        status=InvitationStatus.REVOKED.value,
        revoked_at=now_utc,
        expires_at=now_utc + datetime.timedelta(days=7),
        resend_count=0,
        version=2,
        created_at=now_utc,
        updated_at=now_utc,
    )
    mock_invitation_service.revoke_invitation.return_value = mock_inv

    response = client.delete(f"/api/v1/workspaces/{workspace_id}/invitations/{invitation_id}")

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["status"] == "REVOKED"


def test_verify_invitation_token_api_success(client, mock_invitation_service):
    raw_token = "sec_inv_mocktoken123"
    inv_id = uuid.uuid4()
    ws_id = uuid.uuid4()
    now_utc = datetime.datetime.now(UTC)

    mock_invitation_service.verify_invitation_token.return_value = {
        "invitation_id": inv_id,
        "workspace_id": ws_id,
        "workspace_name": "RAGuard Team",
        "email": "invitee@example.com",
        "role": "MEMBER",
        "inviter_email": "admin@raguard.ai",
        "expires_at": now_utc + datetime.timedelta(days=7),
        "status": "PENDING",
    }

    response = client.get(f"/api/v1/invitations/verify?token={raw_token}")

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["data"]["workspace_name"] == "RAGuard Team"
    assert json_data["data"]["email"] == "invitee@example.com"
    assert json_data["data"]["status"] == "PENDING"
