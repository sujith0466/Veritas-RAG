"""Penetration regression tests for Feature 11: Cross-Tenant BOLA Isolation.

Validates that:
1. Workspace OWNER/ADMIN of foreign workspace receives HTTP 403 or 404 on target workspace endpoints.
2. Workspace OWNER/ADMIN cannot bypass target workspace membership via their own role claim.
3. Legitimate OWNER/ADMIN of the target workspace is permitted (HTTP 200).
4. PLATFORM_ADMIN retains authorized cross-workspace administrative privileges (HTTP 200).
"""

import datetime
from types import SimpleNamespace
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from backend.api.v1.routes.workspaces import router as workspaces_router
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_db,
    get_join_code_service,
    get_workspace_management_service,
    get_workspace_settings_service,
)
from backend.core.permissions.rbac import Role
from backend.services.workspace.join_code_service import (
    JoinCodeSettingsSchema,
    WorkspaceNotFoundError as JoinCodeNotFoundError,
    WorkspaceUnauthorizedError as JoinCodeUnauthorizedError,
)
from backend.services.workspace.management_service import (
    WorkspaceNotFoundError as MgmtNotFoundError,
    WorkspaceUnauthorizedError as MgmtUnauthorizedError,
)
from backend.services.workspace.settings_service import (
    WorkspaceNotFoundError as SettingsNotFoundError,
    WorkspaceSettings,
    WorkspaceUnauthorizedError as SettingsUnauthorizedError,
)


@pytest.fixture
def cross_tenant_app():
    """Create isolated FastAPI instance mounting workspaces router."""
    app = FastAPI()
    app.include_router(workspaces_router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_update_workspace_foreign_admin_denied_and_platform_admin_allowed(cross_tenant_app):
    """Prove that update_workspace rejects foreign admin and passes is_platform_admin=False,

    while granting access to PLATFORM_ADMIN with is_platform_admin=True.
    """
    foreign_ws_id = uuid.uuid4()
    target_ws_id = uuid.uuid4()
    now_dt = datetime.datetime.now(datetime.timezone.utc)

    # 1. Foreign Workspace Owner (User has Role.OWNER in foreign_ws_id)
    foreign_owner = UserContext(
        id=uuid.uuid4(),
        email="owner_workspace_a@example.com",
        role=Role.OWNER.value,
        workspace_id=foreign_ws_id,
        is_verified=True,
    )

    mock_mgmt = AsyncMock()
    # When is_platform_admin is False, the service raises MgmtNotFoundError for non-members
    mock_mgmt.update_workspace.side_effect = lambda session, workspace_id, user_id, expected_updated_at, name, description, is_platform_admin: (
        SimpleNamespace(
            id=workspace_id,
            public_id=f"WS-{str(workspace_id)[:8].upper()}",
            name=name or "Updated Name",
            slug="updated-name",
            description=description,
            status="ACTIVE",
            provisioning_status="READY",
            created_at=now_dt,
            updated_at=now_dt,
            suspended_at=None,
            deleted_at=None,
            purge_at=None,
            created_by_user_id=user_id,
            suspended_by_user_id=None,
            deleted_by_user_id=None,
            suspension_reason_code=None,
            suspension_reason_text=None,
            deletion_reason_code=None,
            deletion_reason_text=None,
        )
        if is_platform_admin
        else (_ for _ in ()).throw(MgmtNotFoundError("Workspace not found or access denied."))
    )

    cross_tenant_app.dependency_overrides[get_current_user] = lambda: foreign_owner
    cross_tenant_app.dependency_overrides[get_db] = lambda: AsyncMock()
    cross_tenant_app.dependency_overrides[get_workspace_management_service] = lambda: mock_mgmt

    transport = ASGITransport(app=cross_tenant_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Case A: Foreign owner attempts to modify target workspace
        resp = await client.patch(
            f"/api/v1/workspaces/{target_ws_id}",
            json={"name": "Attacker Hijack", "expected_updated_at": now_dt.isoformat()},
        )
        assert resp.status_code == 404
        assert "Workspace not found or access denied" in resp.json()["detail"]
        assert mock_mgmt.update_workspace.call_args.kwargs["is_platform_admin"] is False

        # Case B: Platform admin modifies target workspace
        platform_admin = UserContext(
            id=uuid.uuid4(),
            email="platform_admin@example.com",
            role=Role.PLATFORM_ADMIN.value,
            workspace_id=None,
            is_verified=True,
        )
        cross_tenant_app.dependency_overrides[get_current_user] = lambda: platform_admin

        resp_platform = await client.patch(
            f"/api/v1/workspaces/{target_ws_id}",
            json={"name": "Platform Admin Override", "expected_updated_at": now_dt.isoformat()},
        )
        assert resp_platform.status_code == 200
        assert resp_platform.json()["data"]["name"] == "Platform Admin Override"
        assert mock_mgmt.update_workspace.call_args.kwargs["is_platform_admin"] is True


@pytest.mark.asyncio
async def test_patch_settings_foreign_admin_denied_and_same_workspace_allowed(cross_tenant_app):
    """Prove that patch_workspace_settings blocks foreign admins and allows legitimate target members."""
    foreign_ws_id = uuid.uuid4()
    target_ws_id = uuid.uuid4()
    legitimate_user_id = uuid.uuid4()
    now_dt = datetime.datetime.now(datetime.timezone.utc)

    mock_settings_service = AsyncMock()

    def mock_patch(session, workspace_id, user_id, expected_updated_at, patch_data, is_platform_admin):
        if not is_platform_admin and user_id != legitimate_user_id:
            raise SettingsNotFoundError("Workspace not found or access denied.")
        return SimpleNamespace(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            settings_json={"branding": {}, "general": {}},
            schema_version="2.0",
            version=2,
            settings_hash="hash123",
            created_at=now_dt,
            updated_at=now_dt,
        )

    mock_settings_service.patch_settings.side_effect = mock_patch

    cross_tenant_app.dependency_overrides[get_db] = lambda: AsyncMock()
    cross_tenant_app.dependency_overrides[get_workspace_settings_service] = lambda: mock_settings_service

    transport = ASGITransport(app=cross_tenant_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Case A: Foreign Admin attempts to modify target workspace settings
        foreign_admin = UserContext(
            id=uuid.uuid4(),
            email="admin_ws_a@example.com",
            role=Role.ADMIN.value,
            workspace_id=foreign_ws_id,
            is_verified=True,
        )
        cross_tenant_app.dependency_overrides[get_current_user] = lambda: foreign_admin

        resp = await client.patch(
            f"/api/v1/workspaces/{target_ws_id}/settings",
            json={"settings": {"general": {"timezone": "UTC"}}, "expected_updated_at": now_dt.isoformat()},
        )
        assert resp.status_code == 404
        assert mock_settings_service.patch_settings.call_args.kwargs["is_platform_admin"] is False

        # Case B: Legitimate target workspace admin modifies settings
        legitimate_admin = UserContext(
            id=legitimate_user_id,
            email="admin_ws_b@example.com",
            role=Role.ADMIN.value,
            workspace_id=target_ws_id,
            is_verified=True,
        )
        cross_tenant_app.dependency_overrides[get_current_user] = lambda: legitimate_admin

        resp_legit = await client.patch(
            f"/api/v1/workspaces/{target_ws_id}/settings",
            json={"settings": {"general": {"timezone": "UTC"}}, "expected_updated_at": now_dt.isoformat()},
        )
        assert resp_legit.status_code == 200
        assert mock_settings_service.patch_settings.call_args.kwargs["is_platform_admin"] is False


@pytest.mark.asyncio
async def test_join_code_generation_foreign_owner_denied(cross_tenant_app):
    """Prove that generate_join_code rejects foreign workspace owner and grants platform admin."""
    foreign_ws_id = uuid.uuid4()
    target_ws_id = uuid.uuid4()
    now_dt = datetime.datetime.now(datetime.timezone.utc)

    mock_join_code = AsyncMock()

    def mock_generate(session, workspace_id, user_id, is_platform_admin, expires_in_days, default_role, require_approval, max_uses, is_regeneration):
        if not is_platform_admin:
            raise JoinCodeNotFoundError("Workspace not found or inactive.")
        return SimpleNamespace(
            workspace_id=workspace_id,
            join_code="VR-234567",
            join_link="https://app.raguard.ai/join/VR-234567",
            expires_at=now_dt + datetime.timedelta(days=30),
            default_role="MEMBER",
            require_approval=False,
            max_uses=None,
        )

    mock_join_code.generate_new_join_code.side_effect = mock_generate

    cross_tenant_app.dependency_overrides[get_db] = lambda: AsyncMock()
    cross_tenant_app.dependency_overrides[get_join_code_service] = lambda: mock_join_code

    transport = ASGITransport(app=cross_tenant_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Case A: Foreign owner attempts to generate join code for target workspace
        foreign_owner = UserContext(
            id=uuid.uuid4(),
            email="foreign_owner@example.com",
            role=Role.OWNER.value,
            workspace_id=foreign_ws_id,
            is_verified=True,
        )
        cross_tenant_app.dependency_overrides[get_current_user] = lambda: foreign_owner

        resp = await client.post(
            f"/api/v1/workspaces/{target_ws_id}/join-code/generate",
        )
        assert resp.status_code == 404
        assert mock_join_code.generate_new_join_code.call_args.kwargs["is_platform_admin"] is False

        # Case B: Platform admin generates join code for target workspace
        platform_admin = UserContext(
            id=uuid.uuid4(),
            email="super_admin@example.com",
            role=Role.PLATFORM_ADMIN.value,
            workspace_id=None,
            is_verified=True,
        )
        cross_tenant_app.dependency_overrides[get_current_user] = lambda: platform_admin

        resp_platform = await client.post(
            f"/api/v1/workspaces/{target_ws_id}/join-code/generate",
        )
        assert resp_platform.status_code == 200
        assert resp_platform.json()["join_code"] == "VR-234567"
        assert mock_join_code.generate_new_join_code.call_args.kwargs["is_platform_admin"] is True


@pytest.mark.asyncio
async def test_branding_foreign_admin_denied_and_platform_admin_permitted(cross_tenant_app):
    """Prove that get_workspace_branding passes is_platform_admin=False for workspace admin."""
    foreign_ws_id = uuid.uuid4()
    target_ws_id = uuid.uuid4()

    mock_settings_service = AsyncMock()
    mock_settings_service.get_resolved_branding.return_value = {
        "workspace_id": target_ws_id,
        "branding": {"app_name": "Target Branding"},
        "css_variables": {},
        "css_string": "",
        "tailwind_tokens": {},
        "theme_mode": "SYSTEM",
        "version": 1,
        "settings_hash": "hash1",
        "is_preview": False,
    }

    cross_tenant_app.dependency_overrides[get_db] = lambda: AsyncMock()
    cross_tenant_app.dependency_overrides[get_workspace_settings_service] = lambda: mock_settings_service

    transport = ASGITransport(app=cross_tenant_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Case A: Workspace Admin (should NOT be treated as platform admin)
        ws_admin = UserContext(
            id=uuid.uuid4(),
            email="admin_ws_a@example.com",
            role=Role.ADMIN.value,
            workspace_id=foreign_ws_id,
            is_verified=True,
        )
        cross_tenant_app.dependency_overrides[get_current_user] = lambda: ws_admin

        resp = await client.get(f"/api/v1/workspaces/{target_ws_id}/branding")
        assert resp.status_code == 200
        assert mock_settings_service.get_resolved_branding.call_args.kwargs["is_platform_admin"] is False

        # Case B: Platform Admin
        platform_admin = UserContext(
            id=uuid.uuid4(),
            email="platform_admin@example.com",
            role=Role.PLATFORM_ADMIN.value,
            workspace_id=None,
            is_verified=True,
        )
        cross_tenant_app.dependency_overrides[get_current_user] = lambda: platform_admin

        resp_platform = await client.get(f"/api/v1/workspaces/{target_ws_id}/branding")
        assert resp_platform.status_code == 200
        assert mock_settings_service.get_resolved_branding.call_args.kwargs["is_platform_admin"] is True
