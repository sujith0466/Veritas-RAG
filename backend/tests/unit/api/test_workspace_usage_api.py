import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import AsyncClient, ASGITransport

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db as get_db_session
from backend.core.permissions.rbac import Role
from backend.modules.analytics.api.quota_routes import router
from backend.modules.analytics.models.tenant_quota import TenantQuotaORM
from backend.modules.analytics.models.workspace_usage import WorkspaceUsage


@pytest.fixture
def test_app():
    app = FastAPI()
    app.include_router(router, prefix="/analytics")
    return app


@pytest.mark.asyncio
async def test_workspace_usage_rbac_matrix(test_app):
    ws_id = uuid.uuid4()
    p_date = datetime.date(2026, 8, 1)

    roles_allowed = [
        Role.OWNER.value,
        Role.ADMIN.value,
        Role.ANALYST.value,
        Role.PLATFORM_ADMIN.value,
        Role.PLATFORM_SUPPORT.value,
        Role.PLATFORM_AUDITOR.value,
    ]

    roles_forbidden = [
        Role.VIEWER.value,
        Role.MEMBER.value,
        Role.ENGINEER.value,
    ]

    mock_db = AsyncMock()
    test_app.dependency_overrides[get_db_session] = lambda: mock_db

    for role in roles_allowed:
        user_id = uuid.uuid4()
        curr_user = UserContext(id=user_id, email=f"role_{role}@example.com", role=role, workspace_id=ws_id)
        test_app.dependency_overrides[get_current_user] = lambda: curr_user

        with patch("backend.modules.analytics.api.quota_routes.get_workspace_member_or_raise", new_callable=AsyncMock) as mock_auth, \
             patch("backend.modules.analytics.api.quota_routes.UsageRepository") as mock_repo_cls, \
             patch("backend.modules.analytics.api.quota_routes.QuotaGovernor") as mock_gov_cls:
            repo_inst = MagicMock()
            repo_inst.get_current_period_start = MagicMock(return_value=p_date)
            repo_inst.get_current_period_usage = AsyncMock(return_value=WorkspaceUsage(
                workspace_id=ws_id,
                billing_period_start=p_date,
                used_tokens=5000,
                used_queries=10,
            ))
            mock_repo_cls.return_value = repo_inst

            gov_inst = MagicMock()
            gov_inst.get_quota_settings = AsyncMock(return_value=TenantQuotaORM(
                tenant_id=str(ws_id),
                workspace_id=ws_id,
                monthly_token_limit=10000,
                monthly_budget_usd=150.0,
                warning_threshold_pct=0.8,
                is_hard_enforced=True,
            ))
            mock_gov_cls.return_value = gov_inst

            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get(f"/analytics/v1/workspace-usage/{ws_id}")
                assert res.status_code == 200, f"Role {role} should be forbidden with 200, got {res.status_code}"
                data = res.json()
                assert data["used_tokens"] == 5000
                assert data["used_queries"] == 10
                assert data["remaining_tokens"] == 5000
                assert data["is_exceeded"] is False

    for role in roles_forbidden:
        user_id = uuid.uuid4()
        curr_user = UserContext(id=user_id, email=f"forbidden_{role}@example.com", role=role, workspace_id=ws_id)
        test_app.dependency_overrides[get_current_user] = lambda: curr_user

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(f"/analytics/v1/workspace-usage/{ws_id}")
            assert res.status_code == 403, f"Role {role} should be forbidden, got {res.status_code}"

    test_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_workspace_usage_cross_workspace_idor_forbidden(test_app):
    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()
    user_id = uuid.uuid4()

    user_a = UserContext(id=user_id, email="owner_a@example.com", role=Role.OWNER.value, workspace_id=ws_a)
    test_app.dependency_overrides[get_current_user] = lambda: user_a
    test_app.dependency_overrides[get_db_session] = lambda: AsyncMock()

    async def mock_auth(workspace_id, auth, session):
        if workspace_id != ws_a:
            raise HTTPException(status_code=403, detail="Forbidden: You are not a member of this workspace")

    with patch("backend.modules.analytics.api.quota_routes.get_workspace_member_or_raise", side_effect=mock_auth):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # User A attempts accessing Workspace B
            res = await client.get(f"/analytics/v1/workspace-usage/{ws_b}")
            assert res.status_code == 403

    test_app.dependency_overrides.clear()
