"""Unit regression tests for SEC-002: Workspace privilege escalation guards."""
import datetime
from types import SimpleNamespace
import uuid
from unittest.mock import AsyncMock
import pytest
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from httpx import AsyncClient, ASGITransport

from backend.api.v1.routes.workspaces import router
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db, get_workspace_management_service
from backend.core.exceptions.auth import InsufficientRoleException
from backend.core.permissions.rbac import Role


@pytest.fixture
def workspace_app():
    app = FastAPI()

    @app.exception_handler(InsufficientRoleException)
    async def insufficient_role_handler(request, exc):
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    app.include_router(router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize("unauthorized_role", [Role.ADMIN, Role.OWNER, Role.MEMBER])
async def test_sec002_hard_delete_denies_non_platform_admin(workspace_app, unauthorized_role):
    """Prove that hard_delete_workspace rejects Role.ADMIN, Role.OWNER, Role.MEMBER with 403."""
    ws_id = uuid.uuid4()
    user = UserContext(
        id=uuid.uuid4(),
        email="user@example.com",
        role=unauthorized_role.value if hasattr(unauthorized_role, "value") else str(unauthorized_role),
        workspace_id=ws_id,
    )

    workspace_app.dependency_overrides[get_current_user] = lambda: user
    workspace_app.dependency_overrides[get_db] = lambda: AsyncMock()

    transport = ASGITransport(app=workspace_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/workspaces/{ws_id}/hard-delete",
            json={"confirmation_slug": "test-slug", "reason": "Test hard delete", "force_immediate": False},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sec002_hard_delete_permits_platform_admin(workspace_app):
    """Prove that hard_delete_workspace allows Role.PLATFORM_ADMIN."""
    ws_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    platform_admin_user = UserContext(
        id=admin_id,
        email="platform_admin@example.com",
        role=Role.PLATFORM_ADMIN.value,
        workspace_id=ws_id,
    )

    mock_management = AsyncMock()
    mock_management.hard_delete_workspace.return_value = {"deleted": True, "workspace_id": str(ws_id)}

    workspace_app.dependency_overrides[get_current_user] = lambda: platform_admin_user
    workspace_app.dependency_overrides[get_db] = lambda: AsyncMock()
    workspace_app.dependency_overrides[get_workspace_management_service] = lambda: mock_management

    transport = ASGITransport(app=workspace_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/workspaces/{ws_id}/hard-delete",
            json={"confirmation_slug": "test-slug", "reason": "Compliance purge", "force_immediate": True},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_management.hard_delete_workspace.assert_awaited_once_with(
            session=pytest.approx(mock_management.hard_delete_workspace.call_args.kwargs["session"]),
            workspace_id=ws_id,
            admin_id=admin_id,
            confirmation_slug="test-slug",
            reason="Compliance purge",
            force_immediate=True,
        )


@pytest.mark.asyncio
async def test_sec002_soft_delete_differentiates_platform_admin(workspace_app):
    """Prove that soft_delete_workspace passes is_platform_admin=False for Role.ADMIN and True for Role.PLATFORM_ADMIN."""
    ws_id = uuid.uuid4()
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    admin_user = UserContext(
        id=uuid.uuid4(),
        email="admin@example.com",
        role=Role.ADMIN.value,
        workspace_id=ws_id,
    )

    mock_management = AsyncMock()
    fake_ws = SimpleNamespace(
        id=ws_id,
        name="Test Workspace",
        slug="test-workspace",
        description="",
        status="ACTIVE",
        provisioning_status="READY",
        updated_at=now_dt,
        suspended_at=None,
        deleted_at=None,
        purge_at=None,
        deleted_by_user_id=None,
        deletion_reason_code=None,
        deletion_reason_text=None,
    )
    mock_management.soft_delete_workspace.return_value = fake_ws

    workspace_app.dependency_overrides[get_current_user] = lambda: admin_user
    workspace_app.dependency_overrides[get_db] = lambda: AsyncMock()
    workspace_app.dependency_overrides[get_workspace_management_service] = lambda: mock_management

    transport = ASGITransport(app=workspace_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Case 1: Role.ADMIN -> is_platform_admin must be False
        resp = await client.post(
            f"/api/v1/workspaces/{ws_id}/soft-delete",
            json={
                "expected_updated_at": now_dt.isoformat(),
                "confirmation_name": "Test Workspace",
                "reason_code": "USER_REQUESTED",
                "reason_text": "Cleaning up",
            },
        )
        assert resp.status_code == 200
        assert mock_management.soft_delete_workspace.call_args.kwargs["is_platform_admin"] is False

        # Case 2: Role.PLATFORM_ADMIN -> is_platform_admin must be True
        platform_admin = UserContext(
            id=uuid.uuid4(),
            email="platform_admin@example.com",
            role=Role.PLATFORM_ADMIN.value,
            workspace_id=ws_id,
        )
        workspace_app.dependency_overrides[get_current_user] = lambda: platform_admin
        resp2 = await client.post(
            f"/api/v1/workspaces/{ws_id}/soft-delete",
            json={
                "expected_updated_at": now_dt.isoformat(),
                "confirmation_name": "Test Workspace",
                "reason_code": "USER_REQUESTED",
                "reason_text": "Platform cleanup",
            },
        )
        assert resp2.status_code == 200
        assert mock_management.soft_delete_workspace.call_args.kwargs["is_platform_admin"] is True


@pytest.mark.asyncio
async def test_sec002_restore_deleted_workspace_differentiates_platform_admin(workspace_app):
    """Prove that restore_deleted_workspace passes is_platform_admin=False for Role.ADMIN and True for Role.PLATFORM_ADMIN."""
    ws_id = uuid.uuid4()
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    admin_user = UserContext(
        id=uuid.uuid4(),
        email="admin@example.com",
        role=Role.ADMIN.value,
        workspace_id=ws_id,
    )

    mock_management = AsyncMock()
    fake_ws = SimpleNamespace(
        id=ws_id,
        name="Test Workspace",
        slug="test-workspace",
        description="",
        status="ACTIVE",
        provisioning_status="READY",
        updated_at=now_dt,
        suspended_at=None,
        deleted_at=None,
        purge_at=None,
        deleted_by_user_id=None,
        deletion_reason_code=None,
        deletion_reason_text=None,
    )
    mock_management.restore_deleted_workspace.return_value = fake_ws

    workspace_app.dependency_overrides[get_current_user] = lambda: admin_user
    workspace_app.dependency_overrides[get_db] = lambda: AsyncMock()
    workspace_app.dependency_overrides[get_workspace_management_service] = lambda: mock_management

    transport = ASGITransport(app=workspace_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Case 1: Role.ADMIN -> is_platform_admin must be False
        resp = await client.post(
            f"/api/v1/workspaces/{ws_id}/restore-deleted",
            json={"expected_updated_at": now_dt.isoformat()},
        )
        assert resp.status_code == 200
        assert mock_management.restore_deleted_workspace.call_args.kwargs["is_platform_admin"] is False

        # Case 2: Role.PLATFORM_ADMIN -> is_platform_admin must be True
        platform_admin = UserContext(
            id=uuid.uuid4(),
            email="platform_admin@example.com",
            role=Role.PLATFORM_ADMIN.value,
            workspace_id=ws_id,
        )
        workspace_app.dependency_overrides[get_current_user] = lambda: platform_admin
        resp2 = await client.post(
            f"/api/v1/workspaces/{ws_id}/restore-deleted",
            json={"expected_updated_at": now_dt.isoformat()},
        )
        assert resp2.status_code == 200
        assert mock_management.restore_deleted_workspace.call_args.kwargs["is_platform_admin"] is True
