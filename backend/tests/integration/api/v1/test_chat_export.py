import csv
from datetime import UTC, datetime
from io import StringIO
import json
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_db,
    get_workspace_member_repository,
    get_workspace_repository,
)
from backend.core.permissions.rbac import Role
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_member import WorkspaceMember, WorkspaceRole
from backend.modules.chat.api.export_routes import get_chat_repository_with_db, router as export_router
from backend.modules.chat.models import ChatMessage, ChatSession
from backend.modules.chat.repositories.chat_repository import ChatRepository
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository

export_test_app = FastAPI()
export_test_app.include_router(export_router, prefix="/api/v1")


@pytest.fixture
def workspace_id():
    return uuid.uuid4()


def make_user(role: Role = Role.ADMIN, is_platform_admin: bool = False) -> UserContext:
    user = UserContext(
        id=uuid.uuid4(),
        email="test@veritasrag.com",
        role=role,
        is_active=True,
        is_verified=True,
    )
    if is_platform_admin:
        object.__setattr__(user, "is_platform_admin", True)
    return user


def make_chat_message(
    session_id: uuid.UUID,
    message: str = "Hello",
    role: str = "user",
    metadata_json: dict | None = None,
) -> tuple[ChatMessage, uuid.UUID, str]:
    msg = ChatMessage(
        id=uuid.uuid4(),
        session_id=session_id,
        role=role,
        message=message,
        created_at=datetime(2026, 10, 5, 14, 30, 0, tzinfo=UTC),
        citations=[],
        reliability_score=0.95,
        metadata_json=metadata_json or {},
    )
    user_id = uuid.uuid4()
    session_title = "Test Session"
    return (msg, user_id, session_title)


def test_export_chat_history_json_success(workspace_id):
    session_id = uuid.uuid4()
    msg, uid, title = make_chat_message(session_id, message="=1+1 formula test", role="user")

    async def mock_stream(tenant_ids, start_date=None, end_date=None):
        assert str(workspace_id) in tenant_ids
        assert "test-slug" in tenant_ids
        assert end_date.hour == 23 and end_date.minute == 59
        yield (msg, uid, title)

    mock_chat_repo = MagicMock(spec=ChatRepository)
    mock_chat_repo.stream_workspace_messages = mock_stream

    mock_member_repo = AsyncMock(spec=WorkspaceMemberRepository)
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=uuid.uuid4(),
        role=WorkspaceRole.OWNER.value,
    )

    mock_ws_repo = AsyncMock(spec=WorkspaceRepository)
    mock_ws = MagicMock(spec=Workspace)
    mock_ws.slug = "test-slug"
    mock_ws_repo.get_by_id.return_value = mock_ws

    user = make_user(Role.OWNER)
    export_test_app.dependency_overrides[get_current_user] = lambda: user
    export_test_app.dependency_overrides[get_workspace_member_repository] = lambda: mock_member_repo
    export_test_app.dependency_overrides[get_workspace_repository] = lambda: mock_ws_repo
    export_test_app.dependency_overrides[get_chat_repository_with_db] = lambda: mock_chat_repo

    client = TestClient(export_test_app)
    resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/chat/export",
        params={"format": "json", "start_date": "2026-10-05T00:00:00Z", "end_date": "2026-10-05T00:00:00Z"},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    data = resp.json()
    assert len(data) == 1
    assert data[0]["message"] == "=1+1 formula test"
    assert data[0]["session_title"] == "Test Session"


def test_export_chat_history_csv_formula_sanitized(workspace_id):
    session_id = uuid.uuid4()
    msg, uid, title = make_chat_message(session_id, message="=SUM(A1:A10)", role="user")

    async def mock_stream(tenant_ids, start_date=None, end_date=None):
        yield (msg, uid, title)

    mock_chat_repo = MagicMock(spec=ChatRepository)
    mock_chat_repo.stream_workspace_messages = mock_stream

    mock_member_repo = AsyncMock(spec=WorkspaceMemberRepository)
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=uuid.uuid4(),
        role=WorkspaceRole.ADMIN.value,
    )

    mock_ws_repo = AsyncMock(spec=WorkspaceRepository)
    mock_ws_repo.get_by_id.return_value = None

    user = make_user(Role.ADMIN)
    export_test_app.dependency_overrides[get_current_user] = lambda: user
    export_test_app.dependency_overrides[get_workspace_member_repository] = lambda: mock_member_repo
    export_test_app.dependency_overrides[get_workspace_repository] = lambda: mock_ws_repo
    export_test_app.dependency_overrides[get_chat_repository_with_db] = lambda: mock_chat_repo

    client = TestClient(export_test_app)
    resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/chat/export",
        params={"format": "csv"},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    csv_text = resp.text
    reader = list(csv.reader(StringIO(csv_text)))
    assert len(reader) == 2  # header + row
    message_idx = reader[0].index("message")
    # Must be prepended with single quote to prevent formula injection
    assert reader[1][message_idx] == "'=SUM(A1:A10)"


def test_export_chat_history_date_validation_error(workspace_id):
    user = make_user(Role.ADMIN)
    mock_member_repo = AsyncMock(spec=WorkspaceMemberRepository)
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=uuid.uuid4(),
        role=WorkspaceRole.ADMIN.value,
    )

    export_test_app.dependency_overrides[get_current_user] = lambda: user
    export_test_app.dependency_overrides[get_workspace_member_repository] = lambda: mock_member_repo
    export_test_app.dependency_overrides[get_workspace_repository] = lambda: AsyncMock()
    export_test_app.dependency_overrides[get_chat_repository_with_db] = lambda: MagicMock()

    client = TestClient(export_test_app)
    # start_date > end_date
    resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/chat/export",
        params={"format": "json", "start_date": "2026-10-10T00:00:00Z", "end_date": "2026-10-01T00:00:00Z"},
    )

    assert resp.status_code == 400
    assert "Invalid date range: start_date cannot be later than end_date." in resp.text


def test_export_chat_history_platform_admin_bypass(workspace_id):
    mock_chat_repo = MagicMock(spec=ChatRepository)

    async def mock_stream(tenant_ids, start_date=None, end_date=None):
        if False:
            yield

    mock_chat_repo.stream_workspace_messages = mock_stream

    # Member repo returns None (Platform admin is not explicitly in this workspace)
    mock_member_repo = AsyncMock(spec=WorkspaceMemberRepository)
    mock_member_repo.get_membership.return_value = None

    mock_ws_repo = AsyncMock(spec=WorkspaceRepository)
    mock_ws_repo.get_by_id.return_value = None

    # User is platform admin
    user = make_user(role=Role.PLATFORM_ADMIN, is_platform_admin=True)

    export_test_app.dependency_overrides[get_current_user] = lambda: user
    export_test_app.dependency_overrides[get_workspace_member_repository] = lambda: mock_member_repo
    export_test_app.dependency_overrides[get_workspace_repository] = lambda: mock_ws_repo
    export_test_app.dependency_overrides[get_chat_repository_with_db] = lambda: mock_chat_repo

    client = TestClient(export_test_app)
    resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/chat/export",
        params={"format": "json"},
    )

    # Must succeed (200), not 403
    assert resp.status_code == 200


def test_export_chat_history_unauthorized_member_forbidden(workspace_id):
    mock_member_repo = AsyncMock(spec=WorkspaceMemberRepository)
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=uuid.uuid4(),
        role=WorkspaceRole.MEMBER.value,
    )

    user = make_user(Role.MEMBER)

    export_test_app.dependency_overrides[get_current_user] = lambda: user
    export_test_app.dependency_overrides[get_workspace_member_repository] = lambda: mock_member_repo
    export_test_app.dependency_overrides[get_workspace_repository] = lambda: AsyncMock()
    export_test_app.dependency_overrides[get_chat_repository_with_db] = lambda: MagicMock()

    client = TestClient(export_test_app)
    resp = client.get(
        f"/api/v1/workspaces/{workspace_id}/chat/export",
        params={"format": "json"},
    )

    assert resp.status_code == 403
    assert "Only workspace owners and admins can export chat history" in resp.text
