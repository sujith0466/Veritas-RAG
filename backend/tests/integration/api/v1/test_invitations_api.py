"""
Veritas RAG — Section 3: Package T-3.C
API Integration Test Suite: Workspace Invitations Lifecycle & Admission Mapping

Tests FastAPI HTTP status mapping for invitation acceptance, verifying that
admission conflicts (deactivated / inactive user) map strictly to HTTP 409 Conflict.
"""

from unittest.mock import AsyncMock
import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.api.v1.routes.workspace_invitations import invitations_router
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_db,
    get_workspace_invitation_service,
)
from backend.core.permissions.rbac import Role
from backend.services.workspace.invitation_service import (
    InvitationConflictError,
    InvitationInvalidStateError,
    InvitationNotFoundError,
    InvitationUnauthorizedError,
)

app = FastAPI()
app.include_router(invitations_router, prefix="/api/v1")


def get_mock_user() -> UserContext:
    return UserContext(
        id=uuid.uuid4(),
        email="user@example.com",
        role=Role.MEMBER,
        is_active=True,
        is_verified=True,
        supabase_id="mock-supabase-id",
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
    app.dependency_overrides[get_workspace_invitation_service] = lambda: mock_invitation_service
    app.dependency_overrides[get_current_user] = get_mock_user
    app.dependency_overrides[get_db] = lambda: mock_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestInvitationsApiAdmission:
    def test_accept_invitation_success(self, client, mock_invitation_service):
        """Active user accepts invitation successfully (HTTP 200)."""
        ws_id = uuid.uuid4()
        mem_id = uuid.uuid4()
        mock_invitation_service.accept_invitation.return_value = {
            "success": True,
            "workspace_id": ws_id,
            "workspace_name": "Test Workspace",
            "role": "MEMBER",
            "member_id": mem_id,
        }

        response = client.post(
            "/api/v1/invitations/accept",
            json={"token": "sec_inv_mocktoken123_secret123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["member_id"] == str(mem_id)

    def test_accept_invitation_admission_denied_returns_409(self, client, mock_invitation_service):
        """Inactive/deactivated user acceptance triggers admission conflict and returns HTTP 409."""
        mock_invitation_service.accept_invitation.side_effect = InvitationConflictError(
            "Cannot accept invitation: user account is inactive, deleted, or deactivating."
        )

        response = client.post(
            "/api/v1/invitations/accept",
            json={"token": "sec_inv_mocktoken123_secret123"},
        )
        assert response.status_code == 409
        detail = response.json().get("detail", "")
        assert "inactive, deleted, or deactivating" in detail

    def test_accept_invitation_not_found_returns_404(self, client, mock_invitation_service):
        """Non-existent token returns HTTP 404."""
        mock_invitation_service.accept_invitation.side_effect = InvitationNotFoundError(
            "Invalid or non-existent invitation token."
        )
        response = client.post(
            "/api/v1/invitations/accept",
            json={"token": "sec_inv_invalid"},
        )
        assert response.status_code == 404

    def test_accept_invitation_unauthorized_returns_403(self, client, mock_invitation_service):
        """Email mismatch returns HTTP 403."""
        mock_invitation_service.accept_invitation.side_effect = InvitationUnauthorizedError(
            "Logged in user email does not match recipient."
        )
        response = client.post(
            "/api/v1/invitations/accept",
            json={"token": "sec_inv_mismatch"},
        )
        assert response.status_code == 403

    def test_accept_invitation_invalid_state_returns_400(self, client, mock_invitation_service):
        """Expired or already accepted invitation returns HTTP 400."""
        mock_invitation_service.accept_invitation.side_effect = InvitationInvalidStateError(
            "This invitation has expired."
        )
        response = client.post(
            "/api/v1/invitations/accept",
            json={"token": "sec_inv_expired"},
        )
        assert response.status_code == 400
