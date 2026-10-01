import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient, ASGITransport

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db as get_db_session
from backend.core.permissions.rbac import Role
from backend.modules.analytics.api.routes import router as analytics_router
from backend.modules.analytics.schemas.analytics_dto import (
    WorkspaceOverviewDTO,
    PopularTopicDTO,
    UnansweredQueryDTO,
    MostCitedDocumentDTO,
)
from backend.core.exceptions.auth import InsufficientRoleException


def create_analytics_test_app():
    app = FastAPI()

    @app.exception_handler(InsufficientRoleException)
    async def insufficient_role_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    app.include_router(analytics_router, prefix="/api/v1/analytics")
    return app


@pytest.mark.asyncio
async def test_workspace_analytics_rbac_and_tenant_isolation():
    app = create_analytics_test_app()
    transport = ASGITransport(app=app)

    workspace_a = uuid.uuid4()
    workspace_b = uuid.uuid4()

    mock_db = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_db

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test Admin and Owner can access /workspace-overview for workspace A
        for role in [Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN, Role.VIEWER]:
            user = UserContext(
                id=uuid.uuid4(),
                email=f"{role.value}@company.com",
                role=role.value,
                workspace_id=workspace_a,
                tenant_id=str(workspace_a)
            )
            app.dependency_overrides[get_current_user] = lambda u=user: u

            mock_overview = WorkspaceOverviewDTO(
                active_users=42,
                document_count=15,
                total_queries=120,
            )

            with patch("backend.modules.analytics.services.analytics_service.QueryAnalyticsService.get_workspace_overview", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_overview
                res = await client.get("/api/v1/analytics/workspace-overview")
                assert res.status_code == 200, f"Role {role} failed on /workspace-overview: {res.text}"
                data = res.json()["data"]
                assert data["active_users"] == 42
                assert data["document_count"] == 15
                assert data["total_queries"] == 120

                # Verify tenant_id passed to service is strictly workspace_a
                call_args = mock_get.call_args[0][0]
                assert call_args.tenant_id == str(workspace_a), "Service must be called with authenticated workspace ID"
                assert call_args.tenant_id != str(workspace_b), "Cross-tenant leakage detected"

        # 2. Test Popular Topics tenant scoping
        user_a = UserContext(
            id=uuid.uuid4(),
            email="admin@a.com",
            role=Role.ADMIN.value,
            workspace_id=workspace_a,
            tenant_id=str(workspace_a)
        )
        app.dependency_overrides[get_current_user] = lambda: user_a

        with patch("backend.modules.analytics.services.analytics_service.QueryAnalyticsService.get_popular_topics", new_callable=AsyncMock) as mock_topics:
            mock_topics.return_value = [PopularTopicDTO(topic="kubernetes", count=5)]
            res = await client.get("/api/v1/analytics/popular-topics")
            assert res.status_code == 200
            assert res.json()["data"][0]["topic"] == "kubernetes"
            call_args = mock_topics.call_args[0][0]
            assert call_args.tenant_id == str(workspace_a)

        # 3. Test Unanswered Queries tenant scoping
        with patch("backend.modules.analytics.services.analytics_service.QueryAnalyticsService.get_unanswered_queries", new_callable=AsyncMock) as mock_unanswered:
            mock_unanswered.return_value = [
                UnansweredQueryDTO(query_text="What is our 401k match?", outcome="ABORTED_LOW_CONFIDENCE", count=2, last_seen=datetime.now())
            ]
            res = await client.get("/api/v1/analytics/unanswered-queries")
            assert res.status_code == 200
            assert res.json()["data"][0]["query_text"] == "What is our 401k match?"
            call_args = mock_unanswered.call_args[0][0]
            assert call_args.tenant_id == str(workspace_a)

        # 4. Test Most Cited Documents tenant scoping
        with patch("backend.modules.analytics.services.analytics_service.QueryAnalyticsService.get_most_cited_documents", new_callable=AsyncMock) as mock_docs:
            mock_docs.return_value = [
                MostCitedDocumentDTO(
                    document_id=str(uuid.uuid4()),
                    document_title="Security Policy.pdf",
                    citation_count=8,
                    last_cited_at=datetime.now()
                )
            ]
            res = await client.get("/api/v1/analytics/most-cited-documents")
            assert res.status_code == 200
            assert res.json()["data"][0]["document_title"] == "Security Policy.pdf"
            call_args = mock_docs.call_args[0][0]
            assert call_args.tenant_id == str(workspace_a)

        # 5. IDOR test: User B cannot access User A's data
        user_b = UserContext(
            id=uuid.uuid4(),
            email="admin@b.com",
            role=Role.ADMIN.value,
            workspace_id=workspace_b,
            tenant_id=str(workspace_b)
        )
        app.dependency_overrides[get_current_user] = lambda: user_b

        with patch("backend.modules.analytics.services.analytics_service.QueryAnalyticsService.get_workspace_overview", new_callable=AsyncMock) as mock_get_b:
            mock_get_b.return_value = WorkspaceOverviewDTO(active_users=1, document_count=2, total_queries=3)
            res_b = await client.get("/api/v1/analytics/workspace-overview")
            assert res_b.status_code == 200
            call_args_b = mock_get_b.call_args[0][0]
            # Must strictly be workspace_b
            assert call_args_b.tenant_id == str(workspace_b)
            assert call_args_b.tenant_id != str(workspace_a)


@pytest.mark.asyncio
async def test_staleness_report_rbac_and_isolation():
    from backend.api.v1.routes.knowledge_base import router as kb_router
    from backend.modules.knowledge_base.schemas.staleness_dto import StalenessReportDTO

    app = FastAPI()

    @app.exception_handler(InsufficientRoleException)
    async def insufficient_role_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    app.include_router(kb_router, prefix="/api/v1/knowledge-base")

    mock_db = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_db

    workspace_a = uuid.uuid4()
    workspace_b = uuid.uuid4()

    mock_report = StalenessReportDTO(
        workspace_id=workspace_a,
        total_documents=10,
        stale_count=1,
        stale_ratio=0.1,
        aging_distribution={"0-30 days": 9, ">30 days": 1},
        stale_documents=[]
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Admin of workspace A can view workspace A staleness
        user_admin_a = UserContext(id=uuid.uuid4(), email="admin@a.com", role=Role.ADMIN.value, workspace_id=workspace_a)
        app.dependency_overrides[get_current_user] = lambda: user_admin_a

        with patch("backend.modules.knowledge_base.services.staleness_service.StalenessService.get_staleness_report", new_callable=AsyncMock) as mock_stale:
            mock_stale.return_value = mock_report
            res = await client.get(f"/api/v1/knowledge-base/staleness/report?workspace_id={workspace_a}")
            assert res.status_code == 200

        # 2. Owner of workspace A can view workspace A staleness (hierarchy check)
        user_owner_a = UserContext(id=uuid.uuid4(), email="owner@a.com", role=Role.OWNER.value, workspace_id=workspace_a)
        app.dependency_overrides[get_current_user] = lambda: user_owner_a

        with patch("backend.modules.knowledge_base.services.staleness_service.StalenessService.get_staleness_report", new_callable=AsyncMock) as mock_stale:
            mock_stale.return_value = mock_report
            res = await client.get(f"/api/v1/knowledge-base/staleness/report?workspace_id={workspace_a}")
            assert res.status_code == 200

        # 3. Member of workspace A cannot view staleness (requires ADMIN or higher)
        user_member_a = UserContext(id=uuid.uuid4(), email="member@a.com", role=Role.MEMBER.value, workspace_id=workspace_a)
        app.dependency_overrides[get_current_user] = lambda: user_member_a

        res = await client.get(f"/api/v1/knowledge-base/staleness/report?workspace_id={workspace_a}")
        assert res.status_code == 403

        # 4. IDOR: Admin of workspace B cannot view workspace A staleness
        user_admin_b = UserContext(id=uuid.uuid4(), email="admin@b.com", role=Role.ADMIN.value, workspace_id=workspace_b)
        app.dependency_overrides[get_current_user] = lambda: user_admin_b

        res = await client.get(f"/api/v1/knowledge-base/staleness/report?workspace_id={workspace_a}")
        assert res.status_code == 403
