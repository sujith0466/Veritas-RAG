"""
Veritas RAG — Section 3: Package T-3.C
API Integration Test Suite: Access Request Approval Lifecycle & Admission Mapping

Tests FastAPI HTTP status mapping for access request approval, verifying that
admission conflicts (deactivated / inactive user) map strictly to HTTP 409 Conflict.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.api.v1.routes.workspace_access_requests import workspace_access_requests_router
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_access_request_service,
    get_db,
)
from backend.core.permissions.rbac import Role
from backend.services.workspace.access_request_service import (
    AccessRequestConflictError,
    AccessRequestInvalidStateError,
    AccessRequestNotFoundError,
    AccessRequestUnauthorizedError,
)

app = FastAPI()
app.include_router(workspace_access_requests_router, prefix="/api/v1")


def get_mock_admin() -> UserContext:
    return UserContext(
        id=uuid.uuid4(),
        email="admin@example.com",
        role=Role.ADMIN,
        is_active=True,
        is_verified=True,
        supabase_id="mock-admin-supabase-id",
        session_id=uuid.uuid4(),
    )


@pytest.fixture
def mock_access_service():
    return AsyncMock()


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def client(mock_access_service, mock_db_session):
    app.dependency_overrides[get_access_request_service] = lambda: mock_access_service
    app.dependency_overrides[get_current_user] = get_mock_admin
    app.dependency_overrides[get_db] = lambda: mock_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestAccessRequestApiAdmission:
    def test_approve_request_success(self, client, mock_access_service):
        """Admin approves access request successfully (HTTP 200)."""
        ws_id = uuid.uuid4()
        req_id = uuid.uuid4()
        target_user_id = uuid.uuid4()

        mock_req = MagicMock()
        mock_req.id = req_id
        mock_req.workspace_id = ws_id
        mock_req.user_id = target_user_id
        mock_req.request_type = "JOIN_APPROVAL"
        mock_req.current_role = None
        mock_req.requested_role = "MEMBER"
        mock_req.status = "APPROVED"
        mock_req.reason = "Request to join"
        mock_req.reviewed_by_id = uuid.uuid4()
        mock_req.reviewed_at = datetime.now(timezone.utc)
        mock_req.created_at = datetime.now(timezone.utc)
        mock_req.updated_at = datetime.now(timezone.utc)
        mock_req.version = 2
        mock_req.user = None
        mock_req.rejection_reason = None
        mock_access_service.approve_request.return_value = mock_req

        response = client.post(
            f"/api/v1/workspaces/{ws_id}/access-requests/{req_id}/approve"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["request"]["status"] == "APPROVED"

    def test_approve_request_admission_denied_returns_409(self, client, mock_access_service):
        """Approving request for inactive/deactivated user triggers admission conflict (HTTP 409)."""
        ws_id = uuid.uuid4()
        req_id = uuid.uuid4()
        mock_access_service.approve_request.side_effect = AccessRequestConflictError(
            "Cannot approve access request: target user account is inactive or deleted."
        )

        response = client.post(
            f"/api/v1/workspaces/{ws_id}/access-requests/{req_id}/approve"
        )
        assert response.status_code == 409
        detail = response.json().get("detail", "")
        assert "inactive or deleted" in detail

    def test_approve_request_not_found_returns_404(self, client, mock_access_service):
        """Non-existent request returns HTTP 404."""
        ws_id = uuid.uuid4()
        req_id = uuid.uuid4()
        mock_access_service.approve_request.side_effect = AccessRequestNotFoundError(
            "Access request not found."
        )
        response = client.post(
            f"/api/v1/workspaces/{ws_id}/access-requests/{req_id}/approve"
        )
        assert response.status_code == 404

    def test_approve_request_unauthorized_returns_403(self, client, mock_access_service):
        """Unauthorized actor approval attempt returns HTTP 403."""
        ws_id = uuid.uuid4()
        req_id = uuid.uuid4()
        mock_access_service.approve_request.side_effect = AccessRequestUnauthorizedError(
            "Only workspace OWNER or ADMIN can approve access requests."
        )
        response = client.post(
            f"/api/v1/workspaces/{ws_id}/access-requests/{req_id}/approve"
        )
        assert response.status_code == 403

    def test_approve_request_invalid_state_returns_400(self, client, mock_access_service):
        """Inactive workspace or invalid state returns HTTP 400."""
        ws_id = uuid.uuid4()
        req_id = uuid.uuid4()
        mock_access_service.approve_request.side_effect = AccessRequestInvalidStateError(
            "Cannot approve requests for an inactive workspace."
        )
        response = client.post(
            f"/api/v1/workspaces/{ws_id}/access-requests/{req_id}/approve"
        )
        assert response.status_code == 400


class TestAccessRequestApiCreation:
    """T-60: API-level access request submission contract tests."""

    def test_create_access_request_member_success(self, client, mock_access_service):
        """MEMBER access request is accepted and returns HTTP 201."""
        ws_id = uuid.uuid4()
        req_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_req = MagicMock()
        mock_req.id = req_id
        mock_req.workspace_id = ws_id
        mock_req.user_id = user_id
        mock_req.request_type = "ROLE_ELEVATION"
        mock_req.current_role = "VIEWER"
        mock_req.requested_role = "MEMBER"
        mock_req.status = "PENDING"
        mock_req.reason = "Requesting member role"
        mock_req.reviewed_by_id = None
        mock_req.reviewed_at = None
        mock_req.rejection_reason = None
        mock_req.created_at = datetime.now(timezone.utc)
        mock_req.user = None
        mock_access_service.create_request.return_value = mock_req

        response = client.post(
            f"/api/v1/workspaces/{ws_id}/access-requests",
            json={
                "request_type": "ROLE_ELEVATION",
                "requested_role": "MEMBER",
                "reason": "Requesting member role",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["request"]["requested_role"] == "MEMBER"

    @pytest.mark.parametrize(
        "prohibited_role",
        ["ADMIN", "VIEWER", "OWNER", "arbitrary_role", "SUPERUSER"],
    )
    def test_create_access_request_non_member_roles_rejected_422(
        self, client, prohibited_role
    ):
        """T-60: Non-MEMBER requested_role fails schema validation with HTTP 422."""
        ws_id = uuid.uuid4()
        response = client.post(
            f"/api/v1/workspaces/{ws_id}/access-requests",
            json={
                "request_type": "ROLE_ELEVATION",
                "requested_role": prohibited_role,
                "reason": "Attempting non-MEMBER request",
            },
        )
        assert response.status_code == 422
