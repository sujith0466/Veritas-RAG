"""Unit and Route tests for WS-A6 Workspace Switching & Multi-Membership Session Context.

Validates:
1. Target workspace resolution via Public ID, Slug, and Tenant UUID.
2. Server-side membership authorization (non-members and suspended members rejected).
3. Authoritative role derivation from target membership (zero client role trust).
4. Session and token rotation (fresh JWT issued with target workspace_id and role).
5. Invalidation of old access token JTI in Redis blocklist.
6. DB persistence of user's active workspace (user.tenant_id) for refresh continuity.
7. Emission of structured audit logs on switch.
8. Current workspace endpoint (/current) reflecting authoritative active context.
9. Multi-membership listing endpoint (/mine) with active context indicator.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.v1.schemas.workspace_onboarding import (
    CurrentWorkspaceResponse,
    SwitchWorkspaceData,
    SwitchWorkspaceRequest,
    SwitchWorkspaceResponse,
    UserWorkspacesListResponse,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_db,
    get_workspace_member_repository,
    get_workspace_repository,
    get_workspace_switching_service,
)
from backend.core.permissions.rbac import Role
from backend.core.security.jwt import JWTService
from backend.main import app
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.services.workspace.workspace_switching_service import (
    WorkspaceSwitchForbiddenError,
    WorkspaceSwitchNotFoundError,
    WorkspaceSwitchingService,
)


# ── Test Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_user_id():
    return uuid.uuid4()


@pytest.fixture
def mock_ws_a():
    return Workspace(
        id=uuid.uuid4(),
        public_id="WS-ALPHA1",
        name="Alpha Org",
        slug="alpha-org",
        status=WorkspaceStatus.ACTIVE.value,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_ws_b():
    return Workspace(
        id=uuid.uuid4(),
        public_id="WS-BETA02",
        name="Beta Labs",
        slug="beta-labs",
        status=WorkspaceStatus.ACTIVE.value,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


# ── 1. WorkspaceSwitchingService Unit Tests ──────────────────────────────────

@pytest.mark.asyncio
async def test_switch_workspace_success_by_public_id(mock_user_id, mock_ws_b, mock_session):
    """Switching by public ID verifies membership and issues rotated tokens with target role."""
    workspace_repo = AsyncMock(spec=WorkspaceRepository)
    member_repo = AsyncMock(spec=WorkspaceMemberRepository)
    jwt_service = AsyncMock(spec=JWTService)

    workspace_repo.get_by_id.return_value = None
    workspace_repo.get_by_public_id.return_value = mock_ws_b
    workspace_repo.get_by_slug.return_value = None

    membership = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=mock_ws_b.id,
        user_id=mock_user_id,
        role="ADMIN",
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )
    member_repo.get_membership.return_value = membership

    user = User(
        id=mock_user_id,
        email="dev@example.com",
        role="viewer",
        tenant_id="old-ws-uuid",
        is_active=True,
    )
    mock_session.get.return_value = user

    jwt_service.issue_tokens.return_value = ("new.jwt.access", "new-raw-refresh", "family-123")

    service = WorkspaceSwitchingService(workspace_repo, member_repo, jwt_service)

    data, raw_refresh = await service.switch_workspace(
        session=mock_session,
        user_id=mock_user_id,
        workspace_identifier="WS-BETA02",
        current_jti="old-jti-token",
        current_exp=1700000000,
    )

    assert data.workspace_id == mock_ws_b.id
    assert data.workspace_public_id == "WS-BETA02"
    assert data.role == "ADMIN"
    assert data.access_token == "new.jwt.access"
    assert raw_refresh == "new-raw-refresh"
    assert user.tenant_id == str(mock_ws_b.id)
    assert user.workspace_name == "Beta Labs"

    # Verify old token revocation was requested
    jwt_service.revoke_token.assert_awaited_once_with("old-jti-token", 1700000000)
    # Verify audit log was added
    assert mock_session.add.call_count >= 2  # UserSession + AuditLog


@pytest.mark.asyncio
async def test_switch_workspace_success_by_slug(mock_user_id, mock_ws_b, mock_session):
    """Switching by slug resolves workspace and establishes active context."""
    workspace_repo = AsyncMock(spec=WorkspaceRepository)
    member_repo = AsyncMock(spec=WorkspaceMemberRepository)
    jwt_service = AsyncMock(spec=JWTService)

    workspace_repo.get_by_id.return_value = None
    workspace_repo.get_by_public_id.return_value = None
    workspace_repo.get_by_slug.return_value = mock_ws_b

    membership = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=mock_ws_b.id,
        user_id=mock_user_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )
    member_repo.get_membership.return_value = membership

    user = User(
        id=mock_user_id,
        email="dev@example.com",
        role="viewer",
        tenant_id=None,
        is_active=True,
    )
    mock_session.get.return_value = user
    jwt_service.issue_tokens.return_value = ("slug.jwt.token", "raw-refresh-slug", "fam-456")

    service = WorkspaceSwitchingService(workspace_repo, member_repo, jwt_service)

    data, raw_refresh = await service.switch_workspace(
        session=mock_session,
        user_id=mock_user_id,
        workspace_identifier="beta-labs",
    )

    assert data.workspace_id == mock_ws_b.id
    assert data.role == "MEMBER"
    assert user.tenant_id == str(mock_ws_b.id)


@pytest.mark.asyncio
async def test_switch_workspace_target_not_found(mock_user_id, mock_session):
    """Attempting to switch to a non-existent workspace raises WorkspaceSwitchNotFoundError."""
    workspace_repo = AsyncMock(spec=WorkspaceRepository)
    member_repo = AsyncMock(spec=WorkspaceMemberRepository)
    jwt_service = AsyncMock(spec=JWTService)

    workspace_repo.get_by_id.return_value = None
    workspace_repo.get_by_public_id.return_value = None
    workspace_repo.get_by_slug.return_value = None

    service = WorkspaceSwitchingService(workspace_repo, member_repo, jwt_service)

    with pytest.raises(WorkspaceSwitchNotFoundError):
        await service.switch_workspace(
            session=mock_session,
            user_id=mock_user_id,
            workspace_identifier="NON-EXISTENT",
        )


@pytest.mark.asyncio
async def test_switch_workspace_non_member_fails_403(mock_user_id, mock_ws_b, mock_session):
    """User who is not a member of the target workspace receives strict denial."""
    workspace_repo = AsyncMock(spec=WorkspaceRepository)
    member_repo = AsyncMock(spec=WorkspaceMemberRepository)
    jwt_service = AsyncMock(spec=JWTService)

    workspace_repo.get_by_id.return_value = mock_ws_b
    member_repo.get_membership.return_value = None  # Not a member

    service = WorkspaceSwitchingService(workspace_repo, member_repo, jwt_service)

    with pytest.raises(WorkspaceSwitchForbiddenError) as exc_info:
        await service.switch_workspace(
            session=mock_session,
            user_id=mock_user_id,
            workspace_identifier=str(mock_ws_b.id),
        )
    assert "not a member" in str(exc_info.value)


@pytest.mark.asyncio
async def test_switch_workspace_suspended_membership_fails_403(mock_user_id, mock_ws_b, mock_session):
    """User with SUSPENDED membership cannot switch into the workspace."""
    workspace_repo = AsyncMock(spec=WorkspaceRepository)
    member_repo = AsyncMock(spec=WorkspaceMemberRepository)
    jwt_service = AsyncMock(spec=JWTService)

    workspace_repo.get_by_id.return_value = mock_ws_b
    membership = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=mock_ws_b.id,
        user_id=mock_user_id,
        role="MEMBER",
        status=MemberStatus.SUSPENDED.value,
        is_deleted=False,
    )
    member_repo.get_membership.return_value = membership

    service = WorkspaceSwitchingService(workspace_repo, member_repo, jwt_service)

    with pytest.raises(WorkspaceSwitchForbiddenError) as exc_info:
        await service.switch_workspace(
            session=mock_session,
            user_id=mock_user_id,
            workspace_identifier=str(mock_ws_b.id),
        )
    assert "suspended" in str(exc_info.value)


@pytest.mark.asyncio
async def test_switch_workspace_role_derivation_downgrade_and_upgrade(mock_user_id, mock_ws_a, mock_ws_b, mock_session):
    """Role is strictly derived from target membership: ADMIN in WS-A switches to MEMBER in WS-B."""
    workspace_repo = AsyncMock(spec=WorkspaceRepository)
    member_repo = AsyncMock(spec=WorkspaceMemberRepository)
    jwt_service = AsyncMock(spec=JWTService)

    workspace_repo.get_by_public_id.return_value = mock_ws_b
    membership_b = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=mock_ws_b.id,
        user_id=mock_user_id,
        role="MEMBER",  # Target role is MEMBER
        status=MemberStatus.ACTIVE.value,
    )
    member_repo.get_membership.return_value = membership_b

    user = User(
        id=mock_user_id,
        email="dev@example.com",
        role="admin",  # Old global/platform role
        tenant_id=str(mock_ws_a.id),
        is_active=True,
    )
    mock_session.get.return_value = user
    jwt_service.issue_tokens.return_value = ("jwt-member", "raw-refresh", "fam-1")

    service = WorkspaceSwitchingService(workspace_repo, member_repo, jwt_service)

    data, _ = await service.switch_workspace(
        session=mock_session,
        user_id=mock_user_id,
        workspace_identifier="WS-BETA02",
    )

    # Must derive target membership role MEMBER (downgraded from previous admin context)
    assert data.role == "MEMBER"
    jwt_service.issue_tokens.assert_awaited_once_with(
        user=user,
        session=mock_session,
        workspace_id=mock_ws_b.id,
        role="MEMBER",
    )


# ── 2. API Route Integration Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_switch_workspace_route_success(mock_user_id, mock_ws_b):
    """POST /api/v1/workspaces/{id}/switch returns 200 and sets refresh cookie."""
    mock_user = UserContext(
        id=mock_user_id,
        email="caller@example.com",
        role=Role.VIEWER,
        tenant_id="old-ws-id",
    )

    mock_switching_service = AsyncMock(spec=WorkspaceSwitchingService)
    mock_switching_service.switch_workspace.return_value = (
        SwitchWorkspaceData(
            workspace_id=mock_ws_b.id,
            workspace_public_id="WS-BETA02",
            workspace_slug="beta-labs",
            workspace_name="Beta Labs",
            role="OWNER",
            access_token="test.switched.jwt",
            token_type="Bearer",
        ),
        "new-refresh-cookie-value",
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_workspace_switching_service] = lambda: mock_switching_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/api/v1/workspaces/{mock_ws_b.id}/switch")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["workspace_id"] == str(mock_ws_b.id)
    assert body["data"]["workspace_public_id"] == "WS-BETA02"
    assert body["data"]["role"] == "OWNER"
    assert body["data"]["access_token"] == "test.switched.jwt"

    # Verify refresh_token cookie was set
    set_cookie = response.headers.get("set-cookie", "")
    assert "refresh_token=new-refresh-cookie-value" in set_cookie
    assert "HttpOnly" in set_cookie


@pytest.mark.asyncio
async def test_switch_workspace_route_forbidden_403(mock_user_id):
    """POST /api/v1/workspaces/{id}/switch returns 403 when user is not a member."""
    mock_user = UserContext(
        id=mock_user_id,
        email="caller@example.com",
        role=Role.VIEWER,
    )

    mock_switching_service = AsyncMock(spec=WorkspaceSwitchingService)
    mock_switching_service.switch_workspace.side_effect = WorkspaceSwitchForbiddenError(
        "You are not a member of this workspace."
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_workspace_switching_service] = lambda: mock_switching_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/workspaces/WS-FOREIGN/switch")

    app.dependency_overrides.clear()

    assert response.status_code == 403
    err_body = response.json()
    err_msg = err_body.get("error", {}).get("message", "") or err_body.get("detail", "")
    assert "not a member" in err_msg


@pytest.mark.asyncio
async def test_get_current_workspace_route(mock_user_id, mock_ws_a):
    """GET /api/v1/workspaces/current returns authoritative active workspace context."""
    mock_user = UserContext(
        id=mock_user_id,
        email="caller@example.com",
        role=Role.ADMIN,
        tenant_id=str(mock_ws_a.id),
    )

    mock_ws_repo = AsyncMock(spec=WorkspaceRepository)
    mock_ws_repo.get_by_id.return_value = mock_ws_a

    mock_member_repo = AsyncMock(spec=WorkspaceMemberRepository)
    membership = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=mock_ws_a.id,
        user_id=mock_user_id,
        role="ADMIN",
        status=MemberStatus.ACTIVE.value,
        joined_at=datetime.now(UTC),
    )
    mock_member_repo.get_membership.return_value = membership

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_workspace_repository] = lambda: mock_ws_repo
    app.dependency_overrides[get_workspace_member_repository] = lambda: mock_member_repo

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/workspaces/current")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["workspace_id"] == str(mock_ws_a.id)
    assert body["data"]["public_id"] == "WS-ALPHA1"
    assert body["data"]["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_get_current_workspace_route_no_context(mock_user_id):
    """GET /api/v1/workspaces/current returns data=null when user has no active workspace."""
    mock_user = UserContext(
        id=mock_user_id,
        email="pending@example.com",
        role=Role.VIEWER,
        tenant_id=None,
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/workspaces/current")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] is None


@pytest.mark.asyncio
async def test_list_my_workspaces_route(mock_user_id, mock_ws_a, mock_ws_b):
    """GET /api/v1/workspaces/mine returns all active memberships with active context flag."""
    mock_user = UserContext(
        id=mock_user_id,
        email="caller@example.com",
        role=Role.MEMBER,
        tenant_id=str(mock_ws_b.id),  # Beta Labs is the active context
    )

    mock_session = AsyncMock()
    mock_exec_result = MagicMock()
    mock_exec_result.all.return_value = [
        (mock_ws_a, "ADMIN", "ACTIVE"),
        (mock_ws_b, "MEMBER", "ACTIVE"),
    ]
    mock_session.execute.return_value = mock_exec_result

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/workspaces/mine")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["total"] == 2
    items = body["items"]
    assert len(items) == 2

    # Alpha Org should NOT be active context
    alpha_item = next(it for it in items if it["workspace_id"] == str(mock_ws_a.id))
    assert alpha_item["is_active_context"] is False
    assert alpha_item["role"] == "ADMIN"

    # Beta Labs SHOULD be active context
    beta_item = next(it for it in items if it["workspace_id"] == str(mock_ws_b.id))
    assert beta_item["is_active_context"] is True
    assert beta_item["role"] == "MEMBER"
