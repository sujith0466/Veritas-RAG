import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.api.v1.routes.domains import router as domains_router
from backend.api.v1.routes.workspace_webhooks import router as webhooks_router
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.dependencies.workspace import require_workspace_admin_or_owner
from backend.core.permissions.rbac import Role
from backend.models.entities.workspace_domain import WorkspaceDomain
from backend.core.exceptions import get_exception_handlers
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.repositories.workspace_member import WorkspaceMemberRepository


test_app = FastAPI()
for exc_class, handler in get_exception_handlers():
    test_app.add_exception_handler(exc_class, handler)

test_app.include_router(domains_router, prefix="/api/v1")
test_app.include_router(webhooks_router, prefix="/api/v1")


@pytest.fixture
def workspace_id():
    return uuid.uuid4()


@pytest.fixture
def mock_db():
    return AsyncMock()


def make_user(role: Role = Role.VIEWER) -> UserContext:
    return UserContext(
        id=uuid.uuid4(),
        email="user@test.com",
        role=role,
        is_active=True,
        is_verified=True,
    )


@pytest.mark.asyncio
async def test_require_workspace_admin_or_owner_platform_admin_bypass(mock_db, workspace_id):
    platform_admin = make_user(Role.PLATFORM_ADMIN)
    result = await require_workspace_admin_or_owner(workspace_id, platform_admin, mock_db)
    assert result is None


@pytest.mark.asyncio
async def test_require_workspace_admin_or_owner_forbidden_for_viewer(monkeypatch, mock_db, workspace_id):
    user = make_user(Role.VIEWER)
    mock_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=user.id,
        role="VIEWER",
        status=MemberStatus.ACTIVE.value,
    )
    async def mock_get_membership(self, workspace_id, user_id, include_suspended=False):
        return mock_member

    monkeypatch.setattr(WorkspaceMemberRepository, "get_membership", mock_get_membership)

    with pytest.raises(HTTPException) as exc:
        await require_workspace_admin_or_owner(workspace_id, user, mock_db)
    assert exc.value.status_code == 403
    assert "Admin or Owner" in exc.value.detail


@pytest.mark.asyncio
async def test_require_workspace_admin_or_owner_success_for_admin_and_owner(monkeypatch, mock_db, workspace_id):
    for role_name in ["ADMIN", "OWNER", "admin ", "owner"]:
        user = make_user(Role.VIEWER)
        mock_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            user_id=user.id,
            role=role_name,
            status=MemberStatus.ACTIVE.value,
        )
        async def mock_get_membership(self, workspace_id, user_id, include_suspended=False):
            return mock_member

        monkeypatch.setattr(WorkspaceMemberRepository, "get_membership", mock_get_membership)

        member = await require_workspace_admin_or_owner(workspace_id, user, mock_db)
        assert member is not None
        assert member.role == role_name


def test_domains_route_unauthenticated(workspace_id):
    client = TestClient(test_app)
    # No auth dependency override -> raises 401 Authentication required
    res = client.get(f"/api/v1/workspaces/{workspace_id}/domains")
    assert res.status_code == 401


def test_webhooks_route_unauthenticated(workspace_id):
    client = TestClient(test_app)
    res = client.get(f"/api/v1/workspaces/{workspace_id}/webhooks")
    assert res.status_code == 401


def test_domains_route_unauthorized_member(monkeypatch, workspace_id, mock_db):
    user = make_user(Role.VIEWER)
    mock_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=user.id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
    )
    async def mock_get_membership(self, workspace_id, user_id, include_suspended=False):
        return mock_member

    monkeypatch.setattr(WorkspaceMemberRepository, "get_membership", mock_get_membership)

    test_app.dependency_overrides[get_current_user] = lambda: user
    test_app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(test_app)
        res = client.get(f"/api/v1/workspaces/{workspace_id}/domains")
        assert res.status_code == 403
    finally:
        test_app.dependency_overrides.clear()


def test_domains_cross_tenant_verification_404(monkeypatch, workspace_id, mock_db):
    user = make_user(Role.ADMIN)
    mock_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=user.id,
        role="ADMIN",
        status=MemberStatus.ACTIVE.value,
    )
    async def mock_get_membership(self, workspace_id, user_id, include_suspended=False):
        return mock_member

    monkeypatch.setattr(WorkspaceMemberRepository, "get_membership", mock_get_membership)

    # Domain belongs to a different workspace
    other_workspace_id = uuid.uuid4()
    foreign_domain = WorkspaceDomain(
        id=uuid.uuid4(),
        workspace_id=other_workspace_id,
        domain_name="example.com",
        status="PENDING",
        verification_token_hash="fakehash",
        token_expires_at=datetime.now(UTC),
    )
    from backend.repositories.domain_repository import WorkspaceDomainRepository
    async def mock_get_by_id(self, domain_id):
        return foreign_domain

    monkeypatch.setattr(WorkspaceDomainRepository, "get_by_id", mock_get_by_id)

    test_app.dependency_overrides[get_current_user] = lambda: user
    test_app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(test_app)
        res = client.post(f"/api/v1/workspaces/{workspace_id}/domains/{foreign_domain.id}/verify")
        assert res.status_code == 404
        assert "Domain not found" in str(res.json())
    finally:
        test_app.dependency_overrides.clear()


def test_webhooks_route_unauthorized_member(monkeypatch, workspace_id, mock_db):
    user = make_user(Role.VIEWER)
    mock_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=user.id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
    )
    async def mock_get_membership(self, workspace_id, user_id, include_suspended=False):
        return mock_member

    monkeypatch.setattr(WorkspaceMemberRepository, "get_membership", mock_get_membership)

    test_app.dependency_overrides[get_current_user] = lambda: user
    test_app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(test_app)
        res = client.get(f"/api/v1/workspaces/{workspace_id}/webhooks")
        assert res.status_code == 403
    finally:
        test_app.dependency_overrides.clear()
