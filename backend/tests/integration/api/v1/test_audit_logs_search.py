from datetime import UTC, datetime, timedelta
import math
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.routes.audit_logs import router as audit_logs_router
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_audit_log_repository
from backend.core.exceptions import get_exception_handlers
from backend.core.permissions.rbac import Role
from backend.models.entities.audit_log import AuditLog
from backend.repositories.interfaces.audit_log_repository import IAuditLogRepository


test_app = FastAPI()
for exc_class, handler in get_exception_handlers():
    test_app.add_exception_handler(exc_class, handler)

test_app.include_router(audit_logs_router, prefix="/api/v1")


@pytest.fixture
def tenant_id():
    return uuid.uuid4()


def make_admin_user(tenant_id: uuid.UUID) -> UserContext:
    return UserContext(
        id=uuid.uuid4(),
        email="admin@test.com",
        role=Role.ADMIN,
        is_active=True,
        is_verified=True,
        tenant_id=str(tenant_id),
    )


def test_list_audit_logs_pagination_and_total_pages(tenant_id):
    mock_repo = AsyncMock(spec=IAuditLogRepository)

    now = datetime.now(UTC)
    mock_logs = [
        AuditLog(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            action="WORKSPACE_SETTINGS_UPDATED",
            resource_type="WORKSPACE_SETTINGS",
            resource_id=str(tenant_id),
            details={"version": 2},
            status="success",
            created_at=now,
        )
    ]
    total_count = 125
    mock_repo.search_logs.return_value = (mock_logs, total_count)

    user = make_admin_user(tenant_id)
    test_app.dependency_overrides[get_current_user] = lambda: user
    test_app.dependency_overrides[get_audit_log_repository] = lambda: mock_repo

    try:
        client = TestClient(test_app)
        res = client.get("/api/v1/audit-logs?page=2&page_size=50")
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) == 1
        pagination = data["pagination"]
        assert pagination["page"] == 2
        assert pagination["size"] == 50
        assert pagination["total_elements"] == 125
        assert pagination["total_pages"] == math.ceil(125 / 50)  # 3 pages
        mock_repo.search_logs.assert_called_once_with(
            tenant_id=tenant_id,
            query=None,
            action=None,
            start_date=None,
            end_date=None,
            skip=50,
            limit=50,
        )
    finally:
        test_app.dependency_overrides.clear()


def test_list_audit_logs_filtering_parameters(tenant_id):
    mock_repo = AsyncMock(spec=IAuditLogRepository)
    mock_repo.search_logs.return_value = ([], 0)

    user = make_admin_user(tenant_id)
    test_app.dependency_overrides[get_current_user] = lambda: user
    test_app.dependency_overrides[get_audit_log_repository] = lambda: mock_repo

    start = "2026-10-01T00:00:00Z"
    end = "2026-10-04T00:00:00Z"

    try:
        client = TestClient(test_app)
        res = client.get(
            f"/api/v1/audit-logs?query=settings&action=WORKSPACE_SETTINGS_UPDATED&start_date={start}&end_date={end}&page=1&page_size=20"
        )
        assert res.status_code == 200
        assert mock_repo.search_logs.call_count == 1
        args, kwargs = mock_repo.search_logs.call_args
        assert kwargs["tenant_id"] == tenant_id
        assert kwargs["query"] == "settings"
        assert kwargs["action"] == "WORKSPACE_SETTINGS_UPDATED"
        assert kwargs["start_date"] is not None
        assert kwargs["end_date"] is not None
        assert kwargs["skip"] == 0
        assert kwargs["limit"] == 20
    finally:
        test_app.dependency_overrides.clear()
