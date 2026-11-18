"""Unit and Security Verification Tests for Section 10 / WP-10.

Verifies:
1. WorkspaceProvisioningGuardMiddleware returns HTTP 423 Locked on /api/v1/documents/upload when status != READY.
2. HTTP 423 Locked on /api/v1/documents/process, /api/v1/chat/*, /api/v1/retrieval/* when status != READY.
3. Fail-Closed on Infrastructure Failure: returns HTTP 503 when database lookup throws an error.
4. Fail-Closed on Missing Workspace: returns HTTP 404 when target workspace does not exist.
5. Path Normalization: double slashes, trailing slashes, and redundant segments cannot bypass guard.
6. Role Matrix: Privileged roles (PLATFORM_ADMIN, OWNER, ADMIN) CANNOT bypass customer readiness locks on ingestion/chat.
7. Diagnostic Bypass: Platform diagnostic routes (/api/v1/platform/*) and system routes (/health, /settings) bypass guard.
"""

import uuid
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.core.auth.context import UserContext
from backend.core.exceptions import get_exception_handlers
from backend.core.middleware.provisioning_guard import (
    WorkspaceProvisioningGuardMiddleware,
    is_route_covered,
    normalize_path,
)
from backend.core.permissions.rbac import Role
from backend.models.entities.workspace import ProvisioningStatus


# ------------------------------------------------------------------------------
# Route Coverage & Path Normalization Tests
# ------------------------------------------------------------------------------

def test_normalize_path_variants():
    """Verify path normalization resolves traversal, redundant slashes, and case."""
    assert normalize_path("//api/v1/documents/upload") == "/api/v1/documents/upload"
    assert normalize_path("/api/v1/documents/upload/") == "/api/v1/documents/upload"
    assert normalize_path("/api/v1/documents/./upload") == "/api/v1/documents/upload"
    assert normalize_path("/API/V1/DOCUMENTS/UPLOAD") == "/api/v1/documents/upload"


def test_is_route_covered_matrix():
    # Covered routes
    assert is_route_covered("/api/v1/documents/upload", "POST") is True
    assert is_route_covered("//api/v1/documents/upload", "POST") is True
    assert is_route_covered("/api/v1/documents/upload/", "POST") is True
    assert is_route_covered("/api/v1/documents/process", "POST") is True
    assert is_route_covered("/api/v1/documents/url", "POST") is True
    assert is_route_covered("/api/v1/documents", "POST") is True
    assert is_route_covered("/api/v1/chat/sessions", "POST") is True
    assert is_route_covered("/api/v1/chat/stream", "GET") is True
    assert is_route_covered("/api/v1/generation/generate", "POST") is True
    assert is_route_covered("/api/v1/ai/completions", "POST") is True
    assert is_route_covered("/api/v1/retrieval/query", "POST") is True

    # Bypass routes
    assert is_route_covered("/api/v1/chat/sessions", "GET") is False
    assert is_route_covered("/api/v1/chat/sessions/123", "GET") is False
    assert is_route_covered("/api/v1/chat/sessions/123/messages", "GET") is False
    assert is_route_covered("/api/v1/platform-admin/workspaces", "GET") is False
    assert is_route_covered("/api/v1/platform/audit-logs/inspect", "GET") is False
    assert is_route_covered("/api/v1/auth/login", "POST") is False
    assert is_route_covered("/api/v1/auth/refresh", "POST") is False
    assert is_route_covered("/api/v1/health", "GET") is False
    assert is_route_covered("/health", "GET") is False
    assert is_route_covered("/metrics", "GET") is False
    assert is_route_covered("/api/v1/workspaces/123/settings", "GET") is False
    assert is_route_covered("/api/v1/workspaces/123/settings", "PATCH") is False


# ------------------------------------------------------------------------------
# Middleware Integration Tests
# ------------------------------------------------------------------------------

def create_test_app() -> FastAPI:
    app = FastAPI()
    for exc_class, handler in get_exception_handlers():
        app.add_exception_handler(exc_class, handler)

    app.add_middleware(WorkspaceProvisioningGuardMiddleware)

    @app.post("/api/v1/documents/upload")
    async def mock_upload(request: Request):
        return {"success": True, "message": "Uploaded"}

    @app.post("/api/v1/documents/process")
    async def mock_process(request: Request):
        return {"success": True, "message": "Processed"}

    @app.post("/api/v1/chat/sessions")
    async def mock_chat(request: Request):
        return {"success": True, "message": "Chat created"}

    @app.get("/api/v1/chat/sessions")
    async def mock_list_chat_sessions(request: Request):
        return {"success": True, "sessions": []}

    @app.post("/api/v1/retrieval/query")
    async def mock_retrieval(request: Request):
        return {"success": True, "message": "Retrieved"}

    @app.get("/api/v1/platform/audit-logs/inspect")
    async def mock_platform_inspect():
        return {"success": True, "message": "Platform Diagnostic Access"}

    @app.get("/api/v1/health")
    async def mock_health():
        return {"status": "ok"}

    @app.patch("/api/v1/workspaces/{ws_id}/settings")
    async def mock_settings(ws_id: str):
        return {"status": "settings updated"}

    return app


@pytest.fixture
def test_app():
    return create_test_app()


@pytest.mark.parametrize("status_val", ["PENDING", "PROVISIONING", "FAILED", "SUSPENDED"])
def test_unready_workspace_upload_locked_http_423(test_app, status_val):
    """Uploading documents to an unready workspace returns HTTP 423 Locked."""
    ws_id = uuid.uuid4()
    test_app.state.mock_workspace_provisioning_status = {ws_id: status_val}

    client = TestClient(test_app)
    res = client.post(
        "/api/v1/documents/upload",
        headers={"X-Workspace-ID": str(ws_id)},
    )
    assert res.status_code == 423
    data = res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "WORKSPACE_PROVISIONING_LOCKED"
    assert "locked until provisioning is ready" in data["error"]["message"].lower()
    assert data["error"]["detail"]["provisioning_status"] == status_val


def test_ready_workspace_upload_allowed(test_app):
    """Uploading documents to a READY workspace succeeds."""
    ws_id = uuid.uuid4()
    test_app.state.mock_workspace_provisioning_status = {ws_id: "READY"}

    client = TestClient(test_app)
    res = client.post(
        "/api/v1/documents/upload",
        headers={"X-Workspace-ID": str(ws_id)},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True


@pytest.mark.parametrize("endpoint", [
    "/api/v1/documents/process",
    "/api/v1/chat/sessions",
    "/api/v1/retrieval/query",
])
def test_unready_workspace_covered_endpoints_locked(test_app, endpoint):
    """Chat, process, and retrieval endpoints return HTTP 423 on unready workspace."""
    ws_id = uuid.uuid4()
    test_app.state.mock_workspace_provisioning_status = {ws_id: "PROVISIONING"}

    client = TestClient(test_app)
    res = client.post(
        endpoint,
        headers={"X-Workspace-ID": str(ws_id)},
    )
    assert res.status_code == 423
    assert res.json()["error"]["code"] == "WORKSPACE_PROVISIONING_LOCKED"


def test_unready_workspace_allows_read_only_chat_sessions_listing(test_app):
    """Historical chat session listing (GET) is allowed even when workspace is unready."""
    ws_id = uuid.uuid4()
    test_app.state.mock_workspace_provisioning_status = {ws_id: "PROVISIONING"}

    client = TestClient(test_app)
    res = client.get(
        "/api/v1/chat/sessions",
        headers={"X-Workspace-ID": str(ws_id)},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True


@pytest.mark.parametrize("role", [
    Role.PLATFORM_ADMIN,
    Role.OWNER,
    Role.ADMIN,
    Role.MEMBER,
])
def test_privileged_roles_cannot_bypass_unready_workspace(role):
    """Verify that NO role, including PLATFORM_ADMIN, can bypass customer workspace readiness."""
    ws_id = uuid.uuid4()
    app = FastAPI()
    app.add_middleware(WorkspaceProvisioningGuardMiddleware)

    @app.middleware("http")
    async def inject_user_context(request: Request, call_next):
        request.state.user_context = UserContext(
            id=uuid.uuid4(),
            email=f"{role.value}@example.com",
            role=role,
            is_active=True,
            is_verified=True,
            tenant_id=str(ws_id),
        )
        return await call_next(request)

    @app.post("/api/v1/documents/upload")
    async def mock_upload():
        return {"success": True, "message": "Uploaded"}

    app.state.mock_workspace_provisioning_status = {ws_id: "PENDING"}

    client = TestClient(app)
    res = client.post("/api/v1/documents/upload")
    assert res.status_code == 423
    assert res.json()["error"]["code"] == "WORKSPACE_PROVISIONING_LOCKED"


def test_platform_diagnostic_routes_bypass_guard(test_app):
    """Platform diagnostic routes (/api/v1/platform/*) bypass readiness enforcement."""
    ws_id = uuid.uuid4()
    test_app.state.mock_workspace_provisioning_status = {ws_id: "FAILED"}

    client = TestClient(test_app)
    res = client.get(
        "/api/v1/platform/audit-logs/inspect",
        headers={"X-Workspace-ID": str(ws_id)},
    )
    assert res.status_code == 200
    assert res.json()["message"] == "Platform Diagnostic Access"


def test_missing_workspace_fails_closed_http_404():
    """Target workspace not found in DB fails closed with HTTP 404."""
    ws_id = uuid.uuid4()
    app = FastAPI()
    app.add_middleware(WorkspaceProvisioningGuardMiddleware)

    @app.post("/api/v1/documents/upload")
    async def mock_upload():
        return {"success": True}

    # Simulate DB returning None for workspace
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=lambda: None))
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_session
    mock_ctx.__aexit__.return_value = None

    with patch("backend.database.engine.get_session_factory", return_value=lambda: mock_ctx):
        client = TestClient(app)
        res = client.post(
            "/api/v1/documents/upload",
            headers={"X-Workspace-ID": str(ws_id)},
        )
        assert res.status_code == 404
        assert res.json()["error"]["code"] == "WORKSPACE_NOT_FOUND"


def test_infrastructure_failure_fails_closed_http_503():
    """Database query exception fails closed with HTTP 503 Service Unavailable."""
    ws_id = uuid.uuid4()
    app = FastAPI()
    app.add_middleware(WorkspaceProvisioningGuardMiddleware)

    @app.post("/api/v1/documents/upload")
    async def mock_upload():
        return {"success": True}

    with patch("backend.database.engine.get_session_factory", side_effect=RuntimeError("Database connection lost")):
        client = TestClient(app)
        res = client.post(
            "/api/v1/documents/upload",
            headers={"X-Workspace-ID": str(ws_id)},
        )
        assert res.status_code == 503
        assert res.json()["error"]["code"] == "WORKSPACE_READINESS_UNAVAILABLE"


def test_bypassed_endpoints_unaffected_by_provisioning_state(test_app):
    """Health check and workspace settings endpoints bypass readiness enforcement."""
    ws_id = uuid.uuid4()
    test_app.state.mock_workspace_provisioning_status = {ws_id: "PENDING"}

    client = TestClient(test_app)
    # Health check bypass
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200

    # Settings bypass
    res_settings = client.patch(
        f"/api/v1/workspaces/{ws_id}/settings",
        headers={"X-Workspace-ID": str(ws_id)},
    )
    assert res_settings.status_code == 200
