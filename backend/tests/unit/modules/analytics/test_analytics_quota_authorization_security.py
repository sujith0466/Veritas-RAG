"""Security test suite for WP-5: Analytics & Quota Authorization (DEC-07).

Verifies:
1. Workspace-wide query analytics are restricted to active database-backed OWNER and ADMIN.
2. ANALYST, MEMBER, and VIEWER roles are strictly denied (HTTP 403).
3. Generic PLATFORM_ADMIN bypass is prohibited on customer query analytics.
4. Missing and malformed workspace contexts fail closed (HTTP 400).
5. Authoritative database membership revalidation blocks stale-token demoted and suspended users.
6. Workspace usage metrics allow OWNER and ADMIN, deny ANALYST, and allow approved platform diagnostic roles.
7. Report export and download enforce strict tenant isolation (HTTP 403).
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.exceptions.auth import AuthenticationException, InsufficientRoleException
from backend.core.permissions.rbac import Role
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.modules.analytics.api.dependencies import get_analytics_service, get_reporting_service
from backend.modules.analytics.api.quota_routes import router as quota_router
from backend.modules.analytics.api.routes import router as analytics_router
from backend.modules.analytics.models.tenant_quota import TenantQuotaORM
from backend.modules.analytics.schemas.analytics_dto import WorkspaceOverviewDTO
from backend.modules.analytics.schemas.reporting_dto import ReportExportRequestDTO, ReportMetadataDTO


@pytest.fixture
def test_app():
    app = FastAPI()

    @app.exception_handler(InsufficientRoleException)
    async def insufficient_role_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationException)
    async def auth_exception_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(exc)})

    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    app.include_router(analytics_router, prefix="/api/v1/analytics")
    return app


@pytest.mark.asyncio
async def test_analytics_allowed_for_owner_and_admin(test_app):
    """OWNER and ADMIN with active DB membership can access query analytics overview."""
    mock_service = AsyncMock()
    mock_service.get_workspace_overview.return_value = WorkspaceOverviewDTO(
        active_users=5, document_count=10, total_queries=100
    )
    test_app.dependency_overrides[get_analytics_service] = lambda: mock_service

    ws_id = uuid.uuid4()
    for role in [Role.OWNER, Role.ADMIN]:
        user_id = uuid.uuid4()
        user = UserContext(
            id=user_id,
            email=f"{role.value.lower()}@test.com",
            role=role.value,
            workspace_id=ws_id,
            tenant_id=str(ws_id),
        )
        test_app.dependency_overrides[get_current_user] = lambda u=user: u

        mock_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=user_id,
            role=role.value.upper(),
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )

        with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem:
            mock_mem.return_value = mock_member
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get("/api/v1/analytics/workspace-overview")
                assert res.status_code == 200, f"Role {role.value} failed to access analytics overview"
                data = res.json()["data"]
                assert data["active_users"] == 5


@pytest.mark.asyncio
async def test_analytics_denied_for_analyst_member_and_viewer(test_app):
    """ANALYST, MEMBER, and VIEWER roles receive 403 Forbidden on analytics overview."""
    ws_id = uuid.uuid4()
    for role in [Role.ANALYST, Role.MEMBER, Role.VIEWER]:
        user_id = uuid.uuid4()
        user = UserContext(
            id=user_id,
            email=f"{role.value.lower()}@test.com",
            role=role.value,
            workspace_id=ws_id,
            tenant_id=str(ws_id),
        )
        test_app.dependency_overrides[get_current_user] = lambda u=user: u

        mock_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=user_id,
            role=role.value.upper(),
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )

        with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem:
            mock_mem.return_value = mock_member
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get("/api/v1/analytics/workspace-overview")
                assert res.status_code == 403, f"Role {role.value} was not blocked from analytics overview"
                assert "Requires workspace Admin or Owner role" in res.json()["detail"]


@pytest.mark.asyncio
async def test_analytics_denied_for_platform_admin_without_membership(test_app):
    """PLATFORM_ADMIN cannot access customer query analytics without an active workspace seat."""
    ws_id = uuid.uuid4()
    platform_user = UserContext(
        id=uuid.uuid4(),
        email="platform_admin@test.com",
        role=Role.PLATFORM_ADMIN.value,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    test_app.dependency_overrides[get_current_user] = lambda: platform_user

    with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem:
        # Platform admin is not a member of this workspace
        mock_mem.return_value = None

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/analytics/workspace-overview")
            assert res.status_code == 403
            assert "not an active member of this workspace" in res.json()["detail"]


@pytest.mark.asyncio
async def test_analytics_fails_closed_on_missing_context(test_app):
    """Request with missing workspace context fails closed with 400 Bad Request."""
    user = UserContext(
        id=uuid.uuid4(),
        email="admin@test.com",
        role=Role.ADMIN.value,
        workspace_id=None,
        tenant_id=None,
    )
    test_app.dependency_overrides[get_current_user] = lambda: user

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/analytics/workspace-overview")
        assert res.status_code == 400
        assert "Missing workspace context" in res.json()["detail"]


@pytest.mark.asyncio
async def test_analytics_fails_closed_on_malformed_uuid(test_app):
    """Request with malformed non-UUID workspace string fails closed with 400 Bad Request."""
    user = UserContext(
        id=uuid.uuid4(),
        email="admin@test.com",
        role=Role.ADMIN.value,
        workspace_id=None,
        tenant_id="invalid-uuid-format!@#",
    )
    test_app.dependency_overrides[get_current_user] = lambda: user

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/analytics/workspace-overview")
        assert res.status_code == 400
        assert "must be a valid UUID" in res.json()["detail"]


@pytest.mark.asyncio
async def test_analytics_db_revalidation_blocks_stale_token_demoted_user(test_app):
    """JWT claiming ADMIN is blocked if database membership has been demoted to MEMBER."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    stale_user = UserContext(
        id=user_id,
        email="demoted@test.com",
        role=Role.ADMIN.value,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    test_app.dependency_overrides[get_current_user] = lambda: stale_user

    mock_db_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )

    with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem:
        mock_mem.return_value = mock_db_member

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/analytics/workspace-overview")
            assert res.status_code == 403
            assert "Requires workspace Admin or Owner role" in res.json()["detail"]


@pytest.mark.asyncio
async def test_analytics_db_revalidation_blocks_suspended_user(test_app):
    """JWT claiming ADMIN is blocked if member status is SUSPENDED."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    user = UserContext(
        id=user_id,
        email="suspended@test.com",
        role=Role.ADMIN.value,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    test_app.dependency_overrides[get_current_user] = lambda: user

    with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem:
        # include_suspended=False causes repository to return None
        mock_mem.return_value = None

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/analytics/workspace-overview")
            assert res.status_code == 403
            assert "not an active member of this workspace" in res.json()["detail"]


@pytest.mark.asyncio
async def test_workspace_usage_allowed_for_owner_and_admin(test_app):
    """OWNER and ADMIN can access workspace-wide usage metrics."""
    ws_id = uuid.uuid4()
    now_utc = datetime.now(UTC)

    mock_quota = TenantQuotaORM(
        workspace_id=ws_id,
        tenant_id=str(ws_id),
        monthly_token_limit=100000,
        monthly_budget_usd=100.0,
        warning_threshold_pct=0.8,
        is_hard_enforced=True,
    )

    for role in [Role.OWNER, Role.ADMIN]:
        user_id = uuid.uuid4()
        user = UserContext(
            id=user_id,
            email=f"{role.value.lower()}@test.com",
            role=role.value,
            workspace_id=ws_id,
            tenant_id=str(ws_id),
        )
        test_app.dependency_overrides[get_current_user] = lambda u=user: u

        mock_member = WorkspaceMember(
            id=uuid.uuid4(),
            workspace_id=ws_id,
            user_id=user_id,
            role=role.value.upper(),
            status=MemberStatus.ACTIVE.value,
            is_deleted=False,
        )

        with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem, \
             patch("backend.modules.analytics.repositories.usage_repository.UsageRepository.get_current_period_start") as mock_start, \
             patch("backend.modules.analytics.repositories.usage_repository.UsageRepository.get_current_period_usage", new_callable=AsyncMock) as mock_usage, \
             patch("backend.modules.analytics.services.quota.QuotaGovernor.get_quota_settings", new_callable=AsyncMock) as mock_gov:

            mock_mem.return_value = mock_member
            mock_start.return_value = now_utc
            mock_usage.return_value = MagicMock(used_tokens=5000, used_queries=20)
            mock_gov.return_value = mock_quota

            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get(f"/api/v1/analytics/v1/workspace-usage/{ws_id}")
                assert res.status_code == 200, f"Role {role.value} failed to access workspace usage"
                data = res.json()
                assert data["used_tokens"] == 5000
                assert data["monthly_token_limit"] == 100000


@pytest.mark.asyncio
async def test_workspace_usage_denied_for_analyst(test_app):
    """ANALYST is strictly denied workspace-wide usage metrics under DEC-07."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    user = UserContext(
        id=user_id,
        email="analyst@test.com",
        role=Role.ANALYST.value,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    test_app.dependency_overrides[get_current_user] = lambda: user

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/v1/analytics/v1/workspace-usage/{ws_id}")
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_workspace_usage_allowed_for_platform_roles(test_app):
    """PLATFORM_ADMIN, PLATFORM_SUPPORT, and PLATFORM_AUDITOR can read aggregate usage metrics."""
    ws_id = uuid.uuid4()
    now_utc = datetime.now(UTC)

    mock_quota = TenantQuotaORM(
        workspace_id=ws_id,
        tenant_id=str(ws_id),
        monthly_token_limit=100000,
        monthly_budget_usd=100.0,
        warning_threshold_pct=0.8,
        is_hard_enforced=True,
    )

    for role in [Role.PLATFORM_ADMIN, Role.PLATFORM_SUPPORT, Role.PLATFORM_AUDITOR]:
        user = UserContext(
            id=uuid.uuid4(),
            email=f"{role.value.lower()}@raguard.ai",
            role=role.value,
            workspace_id=None,
            tenant_id=None,
        )
        test_app.dependency_overrides[get_current_user] = lambda u=user: u

        with patch("backend.modules.analytics.repositories.usage_repository.UsageRepository.get_current_period_start") as mock_start, \
             patch("backend.modules.analytics.repositories.usage_repository.UsageRepository.get_current_period_usage", new_callable=AsyncMock) as mock_usage, \
             patch("backend.modules.analytics.services.quota.QuotaGovernor.get_quota_settings", new_callable=AsyncMock) as mock_gov:

            mock_start.return_value = now_utc
            mock_usage.return_value = MagicMock(used_tokens=2500, used_queries=10)
            mock_gov.return_value = mock_quota

            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get(f"/api/v1/analytics/v1/workspace-usage/{ws_id}")
                assert res.status_code == 200, f"Platform role {role.value} failed to access workspace usage"
                data = res.json()
                assert data["used_tokens"] == 2500


@pytest.mark.asyncio
async def test_workspace_usage_denied_for_member_and_viewer(test_app):
    """MEMBER and VIEWER roles receive 403 Forbidden on workspace usage route."""
    ws_id = uuid.uuid4()

    for role in [Role.MEMBER, Role.VIEWER]:
        user = UserContext(
            id=uuid.uuid4(),
            email=f"{role.value.lower()}@test.com",
            role=role.value,
            workspace_id=ws_id,
            tenant_id=str(ws_id),
        )
        test_app.dependency_overrides[get_current_user] = lambda u=user: u

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(f"/api/v1/analytics/v1/workspace-usage/{ws_id}")
            assert res.status_code == 403, f"Role {role.value} was not blocked from workspace usage"


@pytest.mark.asyncio
async def test_stale_token_demoted_member_blocked_from_workspace_usage(test_app):
    """Caller whose JWT claims ADMIN but whose DB membership was demoted to MEMBER is blocked with 403."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    stale_user = UserContext(
        id=user_id,
        email="demoted@test.com",
        role=Role.ADMIN.value,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    test_app.dependency_overrides[get_current_user] = lambda: stale_user

    mock_db_member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=user_id,
        role="MEMBER",
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )

    with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem:
        mock_mem.return_value = mock_db_member

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(f"/api/v1/analytics/v1/workspace-usage/{ws_id}")
            assert res.status_code == 403
            assert "Requires workspace Admin or Owner role" in res.json()["detail"]


@pytest.mark.asyncio
async def test_cross_tenant_workspace_usage_rejected(test_app):
    """Caller from Workspace A attempting to inspect Workspace B usage is rejected with 403."""
    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()
    user_id = uuid.uuid4()

    admin_a = UserContext(
        id=user_id,
        email="admin_a@test.com",
        role=Role.ADMIN.value,
        workspace_id=ws_a,
        tenant_id=str(ws_a),
    )
    test_app.dependency_overrides[get_current_user] = lambda: admin_a

    with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem:
        mock_mem.return_value = None

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(f"/api/v1/analytics/v1/workspace-usage/{ws_b}")
            assert res.status_code == 403
            assert "not an active member of this workspace" in res.json()["detail"]


@pytest.mark.asyncio
async def test_report_export_and_download_cross_tenant_isolation(test_app):
    """Report export and download enforce strict tenant isolation."""
    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()
    user_a = UserContext(
        id=uuid.uuid4(),
        email="admin_a@test.com",
        role=Role.ADMIN.value,
        workspace_id=ws_a,
        tenant_id=str(ws_a),
    )
    test_app.dependency_overrides[get_current_user] = lambda: user_a

    mock_member_a = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_a,
        user_id=user_a.id,
        role="ADMIN",
        status=MemberStatus.ACTIVE.value,
        is_deleted=False,
    )

    with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_mem:
        mock_mem.return_value = mock_member_a

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Attempt to export report for Workspace B while authenticated to Workspace A
            export_payload = {
                "tenant_id": str(ws_b),
                "report_type": "reliability_audit",
                "date_range": "30d",
            }
            res_export = await client.post("/api/v1/analytics/reports/export", json=export_payload)
            assert res_export.status_code == 403
            assert "Cannot export reports for another workspace" in res_export.json()["detail"]

            # 2. Simulate cached report belonging to Workspace B, attempt download from Workspace A
            from backend.modules.analytics.api.routes import _report_cache
            report_b_id = f"rep_{uuid.uuid4().hex[:8]}"
            meta_b = ReportMetadataDTO(
                report_id=report_b_id,
                tenant_id=str(ws_b),
                report_type="json",
                title="Workspace B Audit Report",
                generated_at=datetime.now(UTC),
                date_range_label="Last 30 days",
                status="READY",
                download_url=f"/api/v1/analytics/reports/download/{report_b_id}",
            )
            _report_cache[report_b_id] = (b'{"test": "cross_tenant_data"}', meta_b)

            res_dl = await client.get(f"/api/v1/analytics/reports/download/{report_b_id}")
            assert res_dl.status_code == 403
            assert "Cannot download report belonging to another workspace" in res_dl.json()["detail"]
