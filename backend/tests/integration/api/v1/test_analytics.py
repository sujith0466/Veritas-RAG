import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from backend.main import create_app
from backend.core.auth.context import UserContext
from backend.core.permissions.rbac import Role
from backend.core.dependencies.auth import get_optional_user, get_current_user
from backend.core.dependencies.database import get_db
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.modules.analytics.api.dependencies import get_analytics_service
from backend.modules.analytics.schemas.analytics_dto import WorkspaceOverviewDTO, AnalyticsFilterDTO

import pytest

app = create_app()

WS_A_ID = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))
WS_B_ID = str(uuid.UUID("22222222-2222-2222-2222-222222222222"))


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_db_and_membership():
    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    with patch("backend.repositories.workspace_member.WorkspaceMemberRepository.get_membership", new_callable=AsyncMock) as mock_get:
        async def _fake_membership(workspace_id, user_id, include_suspended=False, include_deleted=False):
            curr_user_fn = app.dependency_overrides.get(get_current_user)
            if curr_user_fn:
                u = curr_user_fn()
                if str(workspace_id) == str(u.tenant_id):
                    role_str = u.role.value.upper() if isinstance(u.role, Role) else str(u.role).upper()
                    return WorkspaceMember(
                        id=uuid.uuid4(),
                        workspace_id=workspace_id,
                        user_id=u.id,
                        role=role_str,
                        status=MemberStatus.ACTIVE.value,
                        is_deleted=False,
                    )
            return None

        mock_get.side_effect = _fake_membership
        yield


def get_mock_user(workspace: str, role: Role):
    return UserContext(
        id=uuid.uuid4(),
        email="test@raguard.ai",
        role=role,
        is_active=True,
        is_verified=True,
        supabase_id="mock-supabase-id",
        session_id=uuid.uuid4(),
        workspace_id=uuid.UUID(workspace) if workspace else None,
        tenant_id=workspace,
        workspace_name=workspace
    )


def test_cross_tenant_isolation():
    mock_service = AsyncMock()
    mock_service.get_workspace_overview.return_value = WorkspaceOverviewDTO(
        active_users=0, document_count=0, total_queries=0
    )
    app.dependency_overrides[get_analytics_service] = lambda: mock_service

    client = TestClient(app)

    # Authenticate as Workspace A (ADMIN)
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(WS_A_ID, Role.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(WS_A_ID, Role.ADMIN)

    res_a = client.get("/api/v1/analytics/workspace-overview")
    assert res_a.status_code == 200
    call_args_a = mock_service.get_workspace_overview.call_args[0][0]
    assert call_args_a.tenant_id == WS_A_ID, "Workspace A should only query Workspace A's metrics"

    # Authenticate as Workspace B (ADMIN)
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(WS_B_ID, Role.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(WS_B_ID, Role.ADMIN)

    res_b = client.get("/api/v1/analytics/workspace-overview")
    assert res_b.status_code == 200
    call_args_b = mock_service.get_workspace_overview.call_args[0][0]
    assert call_args_b.tenant_id == WS_B_ID, "Workspace B should only query Workspace B's metrics"

    app.dependency_overrides.clear()


def test_authorization_unauthenticated():
    client = TestClient(app)
    # No dependency overrides, meaning no user is logged in
    res = client.get("/api/v1/analytics/workspace-overview")
    assert res.status_code in (401, 403), f"Expected unauthorized, got {res.status_code}"


def test_authorization_insufficient_role():
    client = TestClient(app)

    # MEMBER is rejected from analytics workspace overview
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(WS_A_ID, Role.MEMBER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(WS_A_ID, Role.MEMBER)
    res = client.get("/api/v1/analytics/workspace-overview")
    assert res.status_code == 403, "MEMBER role should be rejected"

    # VIEWER is rejected from analytics workspace overview
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(WS_A_ID, Role.VIEWER)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(WS_A_ID, Role.VIEWER)
    res = client.get("/api/v1/analytics/workspace-overview")
    assert res.status_code == 403, "VIEWER role should be rejected"

    # ANALYST is rejected from analytics workspace overview under DEC-07
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(WS_A_ID, Role.ANALYST)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(WS_A_ID, Role.ANALYST)
    res = client.get("/api/v1/analytics/workspace-overview")
    assert res.status_code == 403, "ANALYST role should be rejected under DEC-07"

    # MEMBER is also rejected from quota route
    res = client.get(f"/api/v1/analytics/v1/quotas/{WS_A_ID}")
    assert res.status_code == 403, "Insufficient role should be rejected from quotas"

    app.dependency_overrides.clear()


def test_authorization_authorized():
    mock_service = AsyncMock()
    mock_service.get_workspace_overview.return_value = WorkspaceOverviewDTO(
        active_users=1, document_count=2, total_queries=3
    )
    app.dependency_overrides[get_analytics_service] = lambda: mock_service

    client = TestClient(app)

    # OWNER and ADMIN are authorized (strict DEC-07)
    for role in [Role.OWNER, Role.ADMIN]:
        app.dependency_overrides[get_optional_user] = lambda r=role: get_mock_user(WS_A_ID, r)
        app.dependency_overrides[get_current_user] = lambda r=role: get_mock_user(WS_A_ID, r)

        res = client.get("/api/v1/analytics/workspace-overview")
        assert res.status_code == 200, f"Authorized {role.value} access should succeed"
        data = res.json()
        assert data["data"]["active_users"] == 1

    app.dependency_overrides.clear()


def test_popular_topics():
    mock_service = AsyncMock()
    mock_service.get_popular_topics.return_value = [{"topic": "holiday", "count": 10}]
    app.dependency_overrides[get_analytics_service] = lambda: mock_service

    client = TestClient(app)

    # Authenticate as Workspace A
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(WS_A_ID, Role.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(WS_A_ID, Role.ADMIN)

    res_a = client.get("/api/v1/analytics/popular-topics")
    assert res_a.status_code == 200
    call_args_a = mock_service.get_popular_topics.call_args[0][0]
    assert call_args_a.tenant_id == WS_A_ID, "Popular topics should isolate by Workspace-A"

    # Authenticate as Workspace B
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(WS_B_ID, Role.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(WS_B_ID, Role.ADMIN)

    res_b = client.get("/api/v1/analytics/popular-topics")
    assert res_b.status_code == 200
    call_args_b = mock_service.get_popular_topics.call_args[0][0]
    assert call_args_b.tenant_id == WS_B_ID, "Popular topics should isolate by Workspace-B"

    app.dependency_overrides.clear()


def test_unanswered_queries():
    mock_service = AsyncMock()
    mock_service.get_unanswered_queries.return_value = [{"query_text": "unknown", "outcome": "CLARIFICATION_REQUIRED", "count": 1, "last_seen": "2026-08-15T00:00:00Z"}]
    app.dependency_overrides[get_analytics_service] = lambda: mock_service

    client = TestClient(app)

    # Authenticate as Workspace A
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(WS_A_ID, Role.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(WS_A_ID, Role.ADMIN)

    res_a = client.get("/api/v1/analytics/unanswered-queries")
    assert res_a.status_code == 200
    call_args_a = mock_service.get_unanswered_queries.call_args[0][0]
    assert call_args_a.tenant_id == WS_A_ID, "Unanswered queries should isolate by Workspace-A"

    # Authenticate as Workspace B
    app.dependency_overrides[get_optional_user] = lambda: get_mock_user(WS_B_ID, Role.ADMIN)
    app.dependency_overrides[get_current_user] = lambda: get_mock_user(WS_B_ID, Role.ADMIN)

    res_b = client.get("/api/v1/analytics/unanswered-queries")
    assert res_b.status_code == 200
    call_args_b = mock_service.get_unanswered_queries.call_args[0][0]
    assert call_args_b.tenant_id == WS_B_ID, "Unanswered queries should isolate by Workspace-B"

    app.dependency_overrides.clear()
