"""
Veritas RAG — Section 3: Package T-3.C
API Integration Test Suite: Member Restore Lifecycle & Admission Mapping

Tests FastAPI HTTP status mapping for workspace member restoration, specifically
verifying that MembershipConflictError (target user deactivated) maps to HTTP 409 Conflict.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.api.v1.routes.workspace_members import workspace_members_router
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_db,
    get_workspace_membership_service,
)
from backend.core.permissions.rbac import Role
from backend.services.workspace.membership_service import (
    MembershipConflictError,
    MembershipInvalidStateError,
    MembershipNotFoundError,
    MembershipUnauthorizedError,
)

app = FastAPI()
app.include_router(workspace_members_router, prefix="/api/v1")


def get_mock_owner() -> UserContext:
    uid = uuid.uuid4()
    return UserContext(
        id=uid,
        email="owner@example.com",
        role=Role.OWNER,
        is_active=True,
        is_verified=True,
        supabase_id="mock-owner-supabase-id",
        session_id=uuid.uuid4(),
    )


@pytest.fixture
def mock_member_service():
    return AsyncMock()


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def client(mock_member_service, mock_db_session):
    app.dependency_overrides[get_workspace_membership_service] = lambda: mock_member_service
    app.dependency_overrides[get_current_user] = get_mock_owner
    app.dependency_overrides[get_db] = lambda: mock_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestMemberRestoreApiAdmission:
    def test_restore_member_success(self, client, mock_member_service):
        """Owner restores suspended member successfully (HTTP 200)."""
        ws_id = uuid.uuid4()
        mem_id = uuid.uuid4()
        target_uid = uuid.uuid4()

        mock_member = MagicMock()
        mock_member.id = mem_id
        mock_member.workspace_id = ws_id
        mock_member.user_id = target_uid
        mock_member.role = "MEMBER"
        mock_member.status = "ACTIVE"
        mock_member.is_deleted = False
        mock_member.created_at = datetime.now(timezone.utc)
        mock_member.updated_at = datetime.now(timezone.utc)
        mock_member.joined_at = datetime.now(timezone.utc)
        mock_member.version = 2
        mock_member.user = None
        mock_member.invited_by_user_id = None
        mock_member.last_active_at = None
        mock_member_service.restore_member.return_value = mock_member

        response = client.post(
            f"/api/v1/workspaces/{ws_id}/members/{mem_id}/restore"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == str(mem_id)
        assert data["data"]["status"] == "ACTIVE"

    def test_restore_member_admission_denied_returns_409(self, client, mock_member_service):
        """Restoring suspended member whose user account is deactivated returns HTTP 409 Conflict."""
        ws_id = uuid.uuid4()
        mem_id = uuid.uuid4()
        mock_member_service.restore_member.side_effect = MembershipConflictError(
            "Cannot restore member: target user account is inactive, deleted, or deactivating."
        )

        response = client.post(
            f"/api/v1/workspaces/{ws_id}/members/{mem_id}/restore"
        )
        assert response.status_code == 409
        detail = response.json().get("detail", "")
        assert "inactive, deleted, or deactivating" in detail

    def test_restore_member_not_found_returns_404(self, client, mock_member_service):
        """Non-existent member returns HTTP 404."""
        ws_id = uuid.uuid4()
        mem_id = uuid.uuid4()
        mock_member_service.restore_member.side_effect = MembershipNotFoundError(
            "Member not found."
        )
        response = client.post(
            f"/api/v1/workspaces/{ws_id}/members/{mem_id}/restore"
        )
        assert response.status_code == 404

    def test_restore_member_unauthorized_returns_403(self, client, mock_member_service):
        """Unauthorized actor restoring member returns HTTP 403."""
        ws_id = uuid.uuid4()
        mem_id = uuid.uuid4()
        mock_member_service.restore_member.side_effect = MembershipUnauthorizedError(
            "Only OWNER or ADMIN can restore suspended members."
        )
        response = client.post(
            f"/api/v1/workspaces/{ws_id}/members/{mem_id}/restore"
        )
        assert response.status_code == 403

    def test_restore_member_invalid_state_returns_400(self, client, mock_member_service):
        """Inactive workspace returns HTTP 400."""
        ws_id = uuid.uuid4()
        mem_id = uuid.uuid4()
        mock_member_service.restore_member.side_effect = MembershipInvalidStateError(
            "Cannot restore members in an inactive workspace."
        )
        response = client.post(
            f"/api/v1/workspaces/{ws_id}/members/{mem_id}/restore"
        )
        assert response.status_code == 400

    def test_patch_member_role_to_owner_returns_400(self, client):
        """T-67: Direct member role PATCH to OWNER must return HTTP 400 Bad Request."""
        ws_id = uuid.uuid4()
        mem_id = uuid.uuid4()
        response = client.patch(
            f"/api/v1/workspaces/{ws_id}/members/{mem_id}/role",
            json={"role": "OWNER"},
        )
        assert response.status_code == 400
        detail = response.json().get("detail", "")
        assert "Direct assignment or promotion to OWNER is not permitted." in detail
