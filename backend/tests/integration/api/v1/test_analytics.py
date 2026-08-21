import uuid
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from backend.main import create_app
from backend.core.auth.context import UserContext
from backend.core.permissions.rbac import Role
from backend.core.dependencies.auth import get_optional_user, get_current_user
from backend.modules.analytics.api.dependencies import get_analytics_service
from backend.modules.analytics.schemas.analytics_dto import WorkspaceOverviewDTO, AnalyticsFilterDTO

app = create_app()

def get_mock_user(workspace: str, role: Role):
    return UserContext(
        id=uuid.uuid4(),
        email="test@raguard.ai",
        role=role,
        is_active=True,
        is_verified=True,
        supabase_id="mock-supabase-id",
        session_id=uuid.uuid4(),
        workspace_name=workspace
    )

def test_cross_tenant_isolation():
    mock_service = AsyncMock()
    mock_service.get_workspace_overview.return_value = WorkspaceOverviewDTO(
        active_users=0, document_count=0, total_queries=0
    )
    app.dependency_overrides[get_analytics_service] = lambda: mock_service

    client = TestClient(app)

    # Authenticate as Workspace A
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user("Workspace-A", Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user("Workspace-A", Role.VIEWER)

    res_a = client.get("/api/v1/analytics/workspace-overview")
    assert res_a.status_code == 200
    call_args_a = mock_service.get_workspace_overview.call_args[0][0]
    assert call_args_a.tenant_id == "Workspace-A", "Workspace A should only query Workspace A's metrics"

    # Authenticate as Workspace B
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user("Workspace-B", Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user("Workspace-B", Role.VIEWER)

    res_b = client.get("/api/v1/analytics/workspace-overview")
    assert res_b.status_code == 200
    call_args_b = mock_service.get_workspace_overview.call_args[0][0]
    assert call_args_b.tenant_id == "Workspace-B", "Workspace B should only query Workspace B's metrics"

    app.dependency_overrides.clear()

def test_authorization_unauthenticated():
    client = TestClient(app)
    # No dependency overrides, meaning no user is logged in
    res = client.get("/api/v1/analytics/workspace-overview")
    assert res.status_code in (401, 403), f"Expected unauthorized, got {res.status_code}"

def test_authorization_insufficient_role():
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user("Workspace-A", Role.MEMBER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user("Workspace-A", Role.MEMBER)
    client = TestClient(app)

    res = client.get("/api/v1/analytics/workspace-overview")
    assert res.status_code == 403, "Insufficient role should be rejected"

    app.dependency_overrides.clear()

def test_authorization_authorized():
    mock_service = AsyncMock()
    mock_service.get_workspace_overview.return_value = WorkspaceOverviewDTO(
        active_users=1, document_count=2, total_queries=3
    )
    app.dependency_overrides[get_analytics_service] = lambda: mock_service
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user("Workspace-A", Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user("Workspace-A", Role.VIEWER)

    client = TestClient(app)
    res = client.get("/api/v1/analytics/workspace-overview")
    assert res.status_code == 200, "Authorized Viewer access should succeed"
    data = res.json()
    assert data["data"]["active_users"] == 1

    app.dependency_overrides.clear()

def test_popular_topics():
    mock_service = AsyncMock()
    mock_service.get_popular_topics.return_value = [{"topic": "holiday", "count": 10}]
    app.dependency_overrides[get_analytics_service] = lambda: mock_service

    client = TestClient(app)

    # Authenticate as Workspace A
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user("Workspace-A", Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user("Workspace-A", Role.VIEWER)

    res_a = client.get("/api/v1/analytics/popular-topics")
    assert res_a.status_code == 200
    call_args_a = mock_service.get_popular_topics.call_args[0][0]
    assert call_args_a.tenant_id == "Workspace-A", "Popular topics should isolate by Workspace-A"

    # Authenticate as Workspace B
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user("Workspace-B", Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user("Workspace-B", Role.VIEWER)

    res_b = client.get("/api/v1/analytics/popular-topics")
    assert res_b.status_code == 200
    call_args_b = mock_service.get_popular_topics.call_args[0][0]
    assert call_args_b.tenant_id == "Workspace-B", "Popular topics should isolate by Workspace-B"

    app.dependency_overrides.clear()

def test_unanswered_queries():
    mock_service = AsyncMock()
    mock_service.get_unanswered_queries.return_value = [{"query_text": "unknown", "outcome": "CLARIFICATION_REQUIRED", "count": 1, "last_seen": "2026-08-15T00:00:00Z"}]
    app.dependency_overrides[get_analytics_service] = lambda: mock_service

    client = TestClient(app)

    # Authenticate as Workspace A
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user("Workspace-A", Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user("Workspace-A", Role.VIEWER)

    res_a = client.get("/api/v1/analytics/unanswered-queries")
    assert res_a.status_code == 200
    call_args_a = mock_service.get_unanswered_queries.call_args[0][0]
    assert call_args_a.tenant_id == "Workspace-A", "Unanswered queries should isolate by Workspace-A"

    # Authenticate as Workspace B
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user("Workspace-B", Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user("Workspace-B", Role.VIEWER)

    res_b = client.get("/api/v1/analytics/unanswered-queries")
    assert res_b.status_code == 200
    call_args_b = mock_service.get_unanswered_queries.call_args[0][0]
    assert call_args_b.tenant_id == "Workspace-B", "Unanswered queries should isolate by Workspace-B"

    app.dependency_overrides.clear()
