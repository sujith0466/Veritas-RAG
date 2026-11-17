"""
Veritas RAG — Section 3: Package T-3.C
API Integration Test Suite: Workspace Join Code Lifecycle & Admission Mapping

Tests FastAPI HTTP status mapping for join-code redemption, verifying that
admission conflicts (deactivated / inactive user) map strictly to HTTP 409 Conflict.
"""

from unittest.mock import AsyncMock
import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.api.v1.routes.workspaces import router as workspaces_router
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_db,
    get_workspace_joining_service,
)
from backend.core.permissions.rbac import Role
from backend.services.workspace.workspace_joining_service import (
    JoinWorkspaceData,
    WorkspaceJoinCodeInvalidError,
    WorkspaceJoinForbiddenError,
    WorkspaceMembershipConflictError,
    WorkspaceTargetNotFoundError,
)

app = FastAPI()
app.include_router(workspaces_router, prefix="/api/v1")


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
def mock_joining_service():
    return AsyncMock()


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def client(mock_joining_service, mock_db_session):
    app.dependency_overrides[get_workspace_joining_service] = lambda: mock_joining_service
    app.dependency_overrides[get_current_user] = get_mock_user
    app.dependency_overrides[get_db] = lambda: mock_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestJoinCodeApiAdmission:
    def test_join_code_success(self, client, mock_joining_service):
        """Active user joins via valid join code successfully (HTTP 200)."""
        ws_id = uuid.uuid4()
        mem_id = uuid.uuid4()
        mock_joining_service.join_workspace.return_value = JoinWorkspaceData(
            workspace_id=ws_id,
            workspace_name="Engineering",
            role="MEMBER",
            status="ACTIVE",
            member_id=mem_id,
        )

        response = client.post(
            "/api/v1/workspaces/join",
            json={"workspace_id": "ws-engineering", "join_code": "VR-234567"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["member_id"] == str(mem_id)

    def test_join_code_admission_denied_returns_409(self, client, mock_joining_service):
        """Deactivated user join-code attempt triggers admission conflict and returns HTTP 409."""
        mock_joining_service.join_workspace.side_effect = WorkspaceMembershipConflictError(
            "Unable to join workspace. User account is inactive, deleted, or deactivating."
        )

        response = client.post(
            "/api/v1/workspaces/join",
            json={"workspace_id": "ws-engineering", "join_code": "VR-234567"},
        )
        assert response.status_code == 409
        detail = response.json().get("detail", "")
        assert "inactive, deleted, or deactivating" in detail

    def test_join_code_target_not_found_returns_404(self, client, mock_joining_service):
        """Non-existent workspace identifier returns HTTP 404."""
        mock_joining_service.join_workspace.side_effect = WorkspaceTargetNotFoundError(
            "Workspace not found."
        )
        response = client.post(
            "/api/v1/workspaces/join",
            json={"workspace_id": "ws-nonexistent", "join_code": "VR-234567"},
        )
        assert response.status_code == 404

    def test_join_code_invalid_code_returns_400(self, client, mock_joining_service):
        """Invalid join code candidate returns HTTP 400."""
        mock_joining_service.join_workspace.side_effect = WorkspaceJoinCodeInvalidError(
            "Invalid join code candidate."
        )
        response = client.post(
            "/api/v1/workspaces/join",
            json={"workspace_id": "ws-engineering", "join_code": "VR-234567"},
        )
        assert response.status_code == 400
