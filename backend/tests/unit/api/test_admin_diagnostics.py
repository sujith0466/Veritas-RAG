"""Unit tests for Admin Document Diagnostics API (`ADR-005 / Phase D2.7`)."""

import uuid
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from backend.api.v1.routes.admin_documents import router as admin_documents_router
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.exceptions.auth import AuthenticationException, InsufficientRoleException
from backend.core.permissions.rbac import Role
from backend.document.services.reconciliation import (
    ReconciliationItem,
    ReconciliationReport,
)


@pytest.fixture
def admin_diagnostics_app():
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
    mock_session.scalar.return_value = 0
    app.dependency_overrides[get_db] = lambda: mock_session
    app.include_router(admin_documents_router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_admin_diagnostics_rbac_denial(admin_diagnostics_app):
    """Verify that VIEWER and MEMBER roles are denied access (403 Forbidden)."""
    tenant_id = str(uuid.uuid4())

    for forbidden_role in [Role.VIEWER, Role.MEMBER]:
        user_ctx = UserContext(
            id=uuid.uuid4(),
            email=f"{forbidden_role.value}@example.com",
            role=forbidden_role,
            tenant_id=tenant_id,
        )
        admin_diagnostics_app.dependency_overrides[get_current_user] = lambda: user_ctx
        transport = ASGITransport(app=admin_diagnostics_app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/admin/documents/pipeline-health")
            assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_admin_diagnostics_pipeline_health_success(admin_diagnostics_app):
    """Verify that ADMIN role receives truthful diagnostics and reconciliation metrics."""
    tenant_id = str(uuid.uuid4())
    admin_user = UserContext(
        id=uuid.uuid4(),
        email="admin@example.com",
        role=Role.ADMIN,
        tenant_id=tenant_id,
    )
    admin_diagnostics_app.dependency_overrides[get_current_user] = lambda: admin_user

    mock_report = ReconciliationReport(
        tenant_id=str(tenant_id),
        dry_run=True,
        scanned_at="2026-10-02T09:00:00Z",
        total_documents=10,
        healthy_count=7,
        class_a_count=1,
        class_b_count=2,
        class_c_count=0,
        other_discrepancy_count=0,
        items=[],
    )

    with patch(
        "backend.api.v1.routes.admin_documents.DocumentReconciliationService.scan_tenant",
        new=AsyncMock(return_value=mock_report),
    ):
        transport = ASGITransport(app=admin_diagnostics_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/admin/documents/pipeline-health")
            assert resp.status_code == status.HTTP_200_OK

            payload = resp.json()
            assert payload["success"] is True
            data = payload["data"]
            assert data["tenant_id"] == str(tenant_id)
            assert data["storage_discrepancies_count"] == 2
            assert data["summary"]["class_a_intact_storage"] == 1
            assert data["summary"]["class_b_missing_storage"] == 2
            assert len(data["recommendations"]) >= 2
            assert data["status"] in ["DEGRADED", "CRITICAL"]


@pytest.mark.asyncio
async def test_admin_diagnostics_workspace_isolation(admin_diagnostics_app):
    """Verify that a workspace admin cannot inspect a different workspace's health."""
    tenant_id = str(uuid.uuid4())
    other_tenant_id = uuid.uuid4()
    admin_user = UserContext(
        id=uuid.uuid4(),
        email="admin@example.com",
        role=Role.ADMIN,
        tenant_id=tenant_id,
    )
    admin_diagnostics_app.dependency_overrides[get_current_user] = lambda: admin_user
    transport = ASGITransport(app=admin_diagnostics_app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            f"/api/v1/admin/documents/pipeline-health?workspace_id={other_tenant_id}"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_admin_diagnostics_dry_run_reconciliation_scan(admin_diagnostics_app):
    """Verify POST /reconcile dry-run works and mutating mode is rejected."""
    tenant_id = str(uuid.uuid4())
    admin_user = UserContext(
        id=uuid.uuid4(),
        email="admin@example.com",
        role=Role.ADMIN,
        tenant_id=tenant_id,
    )
    admin_diagnostics_app.dependency_overrides[get_current_user] = lambda: admin_user

    mock_report = ReconciliationReport(
        tenant_id=str(tenant_id),
        dry_run=True,
        scanned_at="2026-10-02T09:00:00Z",
        total_documents=5,
        healthy_count=5,
        class_a_count=0,
        class_b_count=0,
        class_c_count=0,
        other_discrepancy_count=0,
        items=[],
    )

    with patch(
        "backend.api.v1.routes.admin_documents.DocumentReconciliationService.scan_tenant",
        new=AsyncMock(return_value=mock_report),
    ):
        transport = ASGITransport(app=admin_diagnostics_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Mutating execution must be rejected with 400
            resp_mutating = await client.post("/api/v1/admin/documents/reconcile?dry_run=false")
            assert resp_mutating.status_code == status.HTTP_400_BAD_REQUEST

            # 2. Dry-run JSON report
            resp_dry = await client.post("/api/v1/admin/documents/reconcile?dry_run=true")
            assert resp_dry.status_code == status.HTTP_200_OK
            assert resp_dry.json()["data"]["dry_run"] is True

            # 3. Dry-run Markdown report
            resp_md = await client.post("/api/v1/admin/documents/reconcile?dry_run=true&format=markdown")
            assert resp_md.status_code == status.HTTP_200_OK
            assert "Document Pipeline Reconciliation Report" in resp_md.json()["data"]["report_markdown"]
