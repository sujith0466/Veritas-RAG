"""Integration tests for WS-A5 Join Workspace and Join Intent endpoints.

Endpoints tested:
- POST /api/v1/workspaces/join
- POST /api/v1/auth/join-intent
- GET /api/v1/auth/join-intent/{intent_id}
- GET /api/v1/auth/sso/login/google (preserving intent)
"""

import json
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.v1.schemas.auth import UserContext
from backend.api.v1.schemas.workspace_onboarding import JoinWorkspaceData
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db, get_workspace_joining_service
from backend.main import app
from backend.services.workspace.workspace_joining_service import (
    WorkspaceIdentifierInvalidError,
    WorkspaceJoinCodeInvalidError,
    WorkspaceJoinForbiddenError,
    WorkspaceJoinIntentMismatchError,
    WorkspaceMembershipConflictError,
    WorkspaceTargetNotFoundError,
)


@pytest.fixture
def mock_user():
    return UserContext(
        id=uuid.uuid4(),
        email="testuser@example.com",
        role="member",
        workspace_id=None,
    )


@pytest.fixture
def mock_joining_service():
    return AsyncMock()


# ── POST /api/v1/workspaces/join ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_join_workspace_api_success(mock_user, mock_joining_service):
    target_ws_id = uuid.uuid4()
    mock_joining_service.join_workspace.return_value = JoinWorkspaceData(
        workspace_id=target_ws_id,
        workspace_name="Design Systems",
        role="MEMBER",
        status="ACTIVE",
        member_id=uuid.uuid4(),
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_workspace_joining_service] = lambda: mock_joining_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/workspaces/join",
            json={
                "workspace_id": "DESIGN-SYS",
                "join_code": "VR-234567",
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["workspace_id"] == str(target_ws_id)
    assert data["data"]["workspace_name"] == "Design Systems"
    assert data["data"]["role"] == "MEMBER"


@pytest.mark.asyncio
async def test_join_workspace_api_conflict_409(mock_user, mock_joining_service):
    mock_joining_service.join_workspace.side_effect = WorkspaceMembershipConflictError(
        "User is already an active member of this workspace."
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_workspace_joining_service] = lambda: mock_joining_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/workspaces/join",
            json={
                "workspace_id": "DESIGN-SYS",
                "join_code": "VR-234567",
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert "already an active member" in response.text.lower()


@pytest.mark.asyncio
async def test_join_workspace_api_invalid_code_400(mock_user, mock_joining_service):
    mock_joining_service.join_workspace.side_effect = WorkspaceJoinCodeInvalidError("Invalid join code.")

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_workspace_joining_service] = lambda: mock_joining_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/workspaces/join",
            json={
                "workspace_id": "DESIGN-SYS",
                "join_code": "VR-234568",
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "invalid join code" in response.text.lower()


@pytest.mark.asyncio
async def test_join_workspace_api_rejects_tenant_uuid_422_or_400(mock_user):
    raw_uuid = str(uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: mock_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/workspaces/join",
            json={
                "workspace_id": raw_uuid,
            },
        )

    app.dependency_overrides.clear()

    # Schema validation catches tenant UUID and rejects
    assert response.status_code in (400, 422)


# ── Join Intent Endpoints ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_join_intent_api_success():
    mock_redis = AsyncMock()
    with patch("backend.api.v1.routes.auth.get_redis_client", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/join-intent",
                json={
                    "workspace_id": "ACME-CORP",
                    "join_code": "VR-234567",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "intent_id" in data["data"]
        assert data["data"]["expires_in_seconds"] == 600

        mock_redis.set.assert_awaited_once()
        args = mock_redis.set.await_args
        assert args[0][0].startswith("auth:join_intent:")
        assert args[1]["ex"] == 600


@pytest.mark.asyncio
async def test_get_join_intent_preview_api_hides_secrets():
    mock_redis = AsyncMock()
    intent_id = "test-intent-id"
    cached_intent = {
        "intent_id": intent_id,
        "workspace_id": "ACME-CORP",
        "join_code": "VR-234567",
        "invitation_token": None,
    }
    mock_redis.get.return_value = json.dumps(cached_intent)

    with patch("backend.api.v1.routes.auth.get_redis_client", return_value=mock_redis), \
         patch("backend.repositories.workspace.WorkspaceRepository.get_by_public_id", new_callable=AsyncMock) as mock_get_ws:

        from backend.models.entities.workspace import Workspace
        mock_get_ws.return_value = Workspace(
            id=uuid.uuid4(),
            name="Acme Corporation",
            slug="acme-corp",
            public_id="ACME-CORP",
            status="ACTIVE",
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/auth/join-intent/{intent_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        preview = data["data"]
        assert preview["intent_id"] == intent_id
        assert preview["workspace_name"] == "Acme Corporation"
        assert preview["workspace_id"] == "ACME-CORP"
        assert preview["requires_join_code"] is True
        assert preview["joining_mode"] == "JOIN_CODE"

        # Security invariant: Raw join_code must NEVER appear in response
        assert "VR-234567" not in json.dumps(data)


@pytest.mark.asyncio
async def test_get_join_intent_preview_not_found():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    with patch("backend.api.v1.routes.auth.get_redis_client", return_value=mock_redis):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/auth/join-intent/non-existent-id")

        assert response.status_code == 404
        assert "not found or expired" in response.text.lower()
