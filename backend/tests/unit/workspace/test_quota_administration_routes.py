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
from backend.modules.analytics.models.tenant_quota import TenantQuotaORM
from backend.modules.analytics.models.workspace_user_quota import WorkspaceUserQuotaORM
from backend.modules.analytics.models.workspace_user_usage import WorkspaceUserUsage
from backend.modules.analytics.api.quota_routes import router


@pytest.fixture
def quota_app():
    app = FastAPI()
    app.include_router(router, prefix="/analytics")
    return app


@pytest.mark.asyncio
async def test_admin_can_update_workspace_quota(quota_app):
    """Verify ADMIN role can update workspace quota within policy bounds (WS-B9)."""
    ws_id = uuid.uuid4()
    admin_user = UserContext(
        id=uuid.uuid4(),
        email="admin@veritas.rag",
        role=Role.ADMIN.value,
        workspace_id=ws_id,
    )

    mock_db = AsyncMock()
    mock_res_ws = MagicMock()
    mock_res_ws.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res_ws
    quota_app.dependency_overrides[get_db_session] = lambda: mock_db
    quota_app.dependency_overrides[get_current_user] = lambda: admin_user

    mock_member = MagicMock()
    mock_member.role = "ADMIN"

    existing_quota = TenantQuotaORM(
        tenant_id=str(ws_id),
        workspace_id=ws_id,
        monthly_token_limit=10_000_000,
        monthly_budget_usd=150.0,
        warning_threshold_pct=0.8,
        is_hard_enforced=True,
    )

    with patch("backend.modules.analytics.api.quota_routes.get_workspace_member_or_raise", new_callable=AsyncMock) as mock_auth, \
         patch("backend.modules.analytics.api.quota_routes.QuotaRepository") as mock_repo_cls, \
         patch("backend.modules.analytics.api.quota_routes.QuotaGovernor") as mock_gov_cls:

        mock_auth.return_value = mock_member

        repo_inst = MagicMock()
        repo_inst.get_by_tenant_id = AsyncMock(return_value=existing_quota)
        repo_inst.create_or_update = AsyncMock(return_value=existing_quota)
        mock_repo_cls.return_value = repo_inst

        gov_inst = MagicMock()
        gov_inst.get_durable_usage = AsyncMock(return_value=1_000_000)
        gov_inst.set_remaining_tokens = AsyncMock()
        mock_gov_cls.return_value = gov_inst

        transport = ASGITransport(app=quota_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/analytics/v1/quotas/{ws_id}",
                json={"monthly_token_limit": 20_000_000, "is_hard_enforced": True},
            )

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["monthly_token_limit"] == 10_000_000  # returns updated_quota


@pytest.mark.asyncio
async def test_get_my_user_quota_allowed_for_regular_member(quota_app):
    """Verify regular MEMBER can fetch their own user quota and usage via /me."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    member_user = UserContext(
        id=user_id,
        email="member@veritas.rag",
        role=Role.MEMBER.value,
        workspace_id=ws_id,
    )

    mock_db = AsyncMock()
    mock_res_user = MagicMock()
    mock_user_obj = MagicMock()
    mock_user_obj.email = "member@veritas.rag"
    mock_user_obj.display_name = "Member User"
    mock_res_user.scalar_one_or_none.return_value = mock_user_obj
    mock_db.execute.return_value = mock_res_user
    quota_app.dependency_overrides[get_db_session] = lambda: mock_db
    quota_app.dependency_overrides[get_current_user] = lambda: member_user

    mock_member = MagicMock()
    mock_member.role = "MEMBER"

    uq_orm = WorkspaceUserQuotaORM(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        monthly_token_budget=500_000,
        is_hard_enforced=True,
        warning_threshold_pct=0.80,
    )
    usage_orm = WorkspaceUserUsage(
        workspace_id=ws_id,
        user_id=user_id,
        billing_period_start=datetime.date(2026, 10, 1),
        used_tokens=125_000,
        used_queries=15,
    )

    with patch("backend.modules.analytics.api.quota_routes.get_workspace_member_or_raise", new_callable=AsyncMock) as mock_auth, \
         patch("backend.modules.analytics.repositories.user_quota_repository.UserQuotaRepository.get_user_quota", new_callable=AsyncMock) as mock_get_uq, \
         patch("backend.modules.analytics.repositories.user_quota_repository.UserQuotaRepository.get_user_usage", new_callable=AsyncMock) as mock_get_usage, \
         patch("backend.modules.analytics.api.quota_routes.QuotaGovernor") as mock_gov_cls:

        mock_auth.return_value = mock_member
        mock_get_uq.return_value = uq_orm
        mock_get_usage.return_value = usage_orm

        gov_inst = MagicMock()
        ws_quota = MagicMock()
        ws_quota.monthly_token_limit = 10_000_000
        gov_inst.get_quota_settings = AsyncMock(return_value=ws_quota)
        mock_gov_cls.return_value = gov_inst

        transport = ASGITransport(app=quota_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/analytics/v1/workspace-user-quotas/{ws_id}/me")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["workspace_id"] == str(ws_id)
        assert data["user_id"] == str(user_id)
        assert data["monthly_token_budget"] == 500_000
        assert data["used_tokens"] == 125_000
        assert data["used_queries"] == 15


@pytest.mark.asyncio
async def test_update_user_quota_rejects_exceeding_workspace_ceiling(quota_app):
    """Verify setting a user quota higher than the workspace ceiling is rejected with HTTP 400."""
    ws_id = uuid.uuid4()
    admin_user = UserContext(
        id=uuid.uuid4(),
        email="admin@veritas.rag",
        role=Role.ADMIN.value,
        workspace_id=ws_id,
    )
    target_user_id = uuid.uuid4()

    mock_db = AsyncMock()
    quota_app.dependency_overrides[get_db_session] = lambda: mock_db
    quota_app.dependency_overrides[get_current_user] = lambda: admin_user

    mock_member = MagicMock()
    mock_member.role = "ADMIN"

    target_member = MagicMock()
    target_member.role = "MEMBER"
    target_user = MagicMock()
    target_user.email = "target@veritas.rag"
    target_user.display_name = "Target User"

    # Mock execute for membership check
    mock_res = MagicMock()
    mock_res.first = MagicMock(return_value=(target_member, target_user))
    mock_db.execute = AsyncMock(return_value=mock_res)

    with patch("backend.modules.analytics.api.quota_routes.require_workspace_admin_or_owner", new_callable=AsyncMock) as mock_auth, \
         patch("backend.modules.analytics.api.quota_routes.QuotaGovernor") as mock_gov_cls:

        mock_auth.return_value = mock_member

        gov_inst = MagicMock()
        ws_quota = MagicMock()
        ws_quota.monthly_token_limit = 5_000_000  # Workspace ceiling is 5M
        gov_inst.get_quota_settings = AsyncMock(return_value=ws_quota)
        mock_gov_cls.return_value = gov_inst

        transport = ASGITransport(app=quota_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                f"/analytics/v1/workspace-user-quotas/{ws_id}/{target_user_id}",
                json={"monthly_token_budget": 10_000_000},  # 10M > 5M ceiling!
            )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "cannot exceed workspace token ceiling" in resp.json()["detail"]
