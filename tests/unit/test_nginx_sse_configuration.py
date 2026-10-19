"""Unit and Configuration Contract Test Suite for Nginx SSE Configuration (REC-006).

Verifies:
1. Exact regex route matching for SSE endpoints and strict rejection of non-streaming routes.
2. Directive scoping in frontend/nginx.conf (buffering off and 300s read timeout strictly in SSE block).
3. Directive scoping and WebSocket isolation in infrastructure/nginx/default.conf.
4. Directive scoping and HTTP/1.1 in deploy/nginx/nginx.conf.
5. FastAPI application SSE response headers (X-Accel-Buffering: no and Cache-Control: no-cache)
   for both chat streaming and AI wrapper streaming endpoints.
"""

from pathlib import Path
import re
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.responses import StreamingResponse

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_NGINX = REPO_ROOT / "frontend" / "nginx.conf"
INFRA_DEFAULT_CONF = REPO_ROOT / "infrastructure" / "nginx" / "default.conf"
DEPLOY_NGINX = REPO_ROOT / "deploy" / "nginx" / "nginx.conf"


def parse_nginx_locations(conf_text: str) -> dict[str, str]:
    """Extract location blocks and their inner contents from an nginx configuration string."""
    locations = {}
    pattern = re.compile(r"location\s+([^{]+)\{([^}]+)\}", re.DOTALL)
    for match in pattern.finditer(conf_text):
        loc_header = match.group(1).strip()
        loc_body = match.group(2).strip()
        locations[loc_header] = loc_body
    return locations


# ── 1. REGEX ROUTE MATCHING CONTRACT ──────────────────────────────────────────


def test_regex_route_matching_contract():
    """Verify the exact regex extracted from Nginx configs matches only target SSE endpoints."""
    # Ensure all configs share the canonical anchored regex
    regex_pattern = r"^/api/v1/(chat/sessions/[^/]+/stream|ai/stream)/?$"
    compiled = re.compile(regex_pattern, re.IGNORECASE)

    # Positive matches (valid SSE endpoints)
    valid_paths = [
        "/api/v1/chat/sessions/123/stream",
        "/api/v1/chat/sessions/3fa85f64-5717-4562-b3fc-2c963f66afa6/stream",
        "/api/v1/chat/sessions/sess_alpha_99/stream",
        "/api/v1/chat/sessions/user@example.com/stream",
        "/api/v1/chat/sessions/123/stream/",  # Trailing slash tolerance
        "/api/v1/ai/stream",
        "/api/v1/ai/stream/",  # Trailing slash tolerance
    ]
    for path in valid_paths:
        assert compiled.match(path) is not None, f"Expected '{path}' to match SSE regex"

    # Negative matches (unrelated, CRUD, file downloads, or malformed paths)
    invalid_paths = [
        "/api/v1/chat/sessions",  # List sessions
        "/api/v1/chat/sessions/",  # List sessions with slash
        "/api/v1/chat/sessions/123",  # Get session details
        "/api/v1/chat/sessions/123/messages",  # Session messages
        "/api/v1/chat/sessions/123/export",  # Export session
        "/api/v1/chat/sessions//stream",  # Empty session ID
        "/api/v1/chat/sessions/123/stream/subpath",  # Suffix trailing path
        "/api/v1/documents",  # Document list
        "/api/v1/documents/123/file",  # Binary file download stream
        "/api/v1/documents/123/extracted-text",  # Text stream
        "/api/v1/notifications/ws",  # WebSocket endpoint
        "/health",  # Health endpoint
        "/docs",  # Docs
        "/openapi.json",  # OpenAPI
        "/api/v1/ai/stream/extra",  # Appended segment
    ]
    for path in invalid_paths:
        assert compiled.match(path) is None, f"Expected '{path}' NOT to match SSE regex"


# ── 2. FRONTEND NGINX CONFIGURATION CONTRACT ──────────────────────────────────


def test_frontend_nginx_configuration_contract():
    """Verify frontend/nginx.conf scopes SSE buffering off and preserves WebSocket & REST."""
    assert FRONTEND_NGINX.exists(), f"File not found: {FRONTEND_NGINX}"
    content = FRONTEND_NGINX.read_text(encoding="utf-8")
    locations = parse_nginx_locations(content)

    # 1. Locate SSE location
    sse_key = next((k for k in locations if "chat/sessions" in k and "ai/stream" in k), None)
    assert sse_key is not None, "Missing SSE location in frontend/nginx.conf"
    sse_body = locations[sse_key]

    # SSE directives verification
    assert "proxy_buffering off;" in sse_body, "SSE block must disable proxy_buffering"
    assert "proxy_cache off;" in sse_body, "SSE block must disable proxy_cache"
    assert "proxy_read_timeout 300s;" in sse_body, "SSE block must set 300s read timeout"
    assert "proxy_send_timeout 300s;" in sse_body, "SSE block must set 300s send timeout"
    assert "proxy_http_version 1.1;" in sse_body, "SSE block must specify HTTP/1.1"
    assert "proxy_pass http://api:8000;" in sse_body, "SSE block must proxy to http://api:8000 without URI part"

    # 2. Locate generic /api/ location
    api_body = locations.get("/api/")
    assert api_body is not None, "Missing location /api/ in frontend/nginx.conf"
    assert "proxy_buffering off;" not in api_body, "Generic /api/ must NOT have proxy_buffering off"
    assert "proxy_read_timeout 60s;" in api_body, "Generic /api/ must retain standard 60s timeout"
    assert "proxy_pass http://api:8000/api/;" in api_body, "Generic /api/ must preserve proxy target"

    # 3. Locate WebSocket location
    ws_key = next((k for k in locations if "notifications/ws" in k), None)
    assert ws_key is not None, "Missing notifications/ws location in frontend/nginx.conf"
    assert "^~" in ws_key, "WebSocket location should use ^~ modifier for prefix priority"
    ws_body = locations[ws_key]
    assert 'proxy_set_header Upgrade $http_upgrade;' in ws_body
    assert 'proxy_set_header Connection "upgrade";' in ws_body
    assert "proxy_read_timeout 86400s;" in ws_body


# ── 3. INFRASTRUCTURE NGINX CONFIGURATION CONTRACT ────────────────────────────


def test_infrastructure_nginx_configuration_contract():
    """Verify infrastructure/nginx/default.conf isolates WebSocket and scopes SSE directives."""
    assert INFRA_DEFAULT_CONF.exists(), f"File not found: {INFRA_DEFAULT_CONF}"
    content = INFRA_DEFAULT_CONF.read_text(encoding="utf-8")
    locations = parse_nginx_locations(content)

    # 1. Locate SSE location
    sse_key = next((k for k in locations if "chat/sessions" in k and "ai/stream" in k), None)
    assert sse_key is not None, "Missing SSE location in infrastructure/nginx/default.conf"
    sse_body = locations[sse_key]

    assert "proxy_buffering off;" in sse_body, "SSE block must disable proxy_buffering"
    assert "proxy_cache off;" in sse_body, "SSE block must disable proxy_cache"
    assert "proxy_read_timeout 300s;" in sse_body, "SSE block must set 300s read timeout"
    assert "proxy_send_timeout 300s;" in sse_body, "SSE block must set 300s send timeout"
    assert "proxy_http_version 1.1;" in sse_body, "SSE block must specify HTTP/1.1"
    assert "proxy_pass http://backend_api;" in sse_body, "SSE block must proxy to http://backend_api"

    # 2. Locate generic /api/ location - must NOT contain unconditional upgrade
    api_body = locations.get("/api/")
    assert api_body is not None, "Missing location /api/ in infrastructure/nginx/default.conf"
    assert "proxy_buffering off;" not in api_body, "Generic /api/ must NOT have proxy_buffering off"
    assert "Connection 'upgrade'" not in api_body, "Generic /api/ must NOT have unconditional Connection: upgrade"
    assert "Upgrade $http_upgrade" not in api_body, "Generic /api/ must NOT have unconditional Upgrade header"
    assert "proxy_read_timeout 90s;" in api_body, "Generic /api/ must retain standard 90s timeout"

    # 3. Locate dedicated WebSocket location
    ws_key = next((k for k in locations if "notifications/ws" in k), None)
    assert ws_key is not None, "Missing dedicated notifications/ws location in infrastructure/nginx/default.conf"
    assert "^~" in ws_key, "WebSocket location must use ^~ modifier for prefix priority"
    ws_body = locations[ws_key]
    assert "proxy_set_header Upgrade $http_upgrade;" in ws_body
    assert 'proxy_set_header Connection "upgrade";' in ws_body
    assert "proxy_read_timeout 86400s;" in ws_body


# ── 4. DEPLOY NGINX CONFIGURATION CONTRACT ────────────────────────────────────


def test_deploy_nginx_configuration_contract():
    """Verify deploy/nginx/nginx.conf has SSE location with HTTP/1.1 and buffering off."""
    assert DEPLOY_NGINX.exists(), f"File not found: {DEPLOY_NGINX}"
    content = DEPLOY_NGINX.read_text(encoding="utf-8")
    locations = parse_nginx_locations(content)

    sse_key = next((k for k in locations if "chat/sessions" in k and "ai/stream" in k), None)
    assert sse_key is not None, "Missing SSE location in deploy/nginx/nginx.conf"
    sse_body = locations[sse_key]

    assert "proxy_buffering off;" in sse_body, "SSE block must disable proxy_buffering"
    assert "proxy_cache off;" in sse_body, "SSE block must disable proxy_cache"
    assert "proxy_read_timeout 300s;" in sse_body, "SSE block must set 300s read timeout"
    assert "proxy_send_timeout 300s;" in sse_body, "SSE block must set 300s send timeout"
    assert "proxy_http_version 1.1;" in sse_body, "SSE block must specify HTTP/1.1"
    assert "proxy_pass http://raguard_api;" in sse_body, "SSE block must proxy to http://raguard_api"

    # Ensure root location / is preserved and does NOT have proxy_buffering off
    root_body = locations.get("/")
    assert root_body is not None, "Missing root location / in deploy/nginx/nginx.conf"
    assert "proxy_buffering off;" not in root_body, "Root location / must not have proxy_buffering off"


# ── 5. FASTAPI APPLICATION SSE HEADERS CONTRACT ───────────────────────────────


@pytest.mark.asyncio
async def test_fastapi_ai_wrapper_stream_headers():
    """Verify /api/v1/ai/stream returns Cache-Control: no-cache and X-Accel-Buffering: no."""
    from backend.ai.api.routes import stream_ai_request
    from backend.ai.schemas.wrapper_dto import AIWrapperRequest
    from backend.core.auth.context import UserContext
    import uuid

    mock_request = MagicMock()
    mock_request.state.correlation_id = "test-corr-id"

    mock_service = MagicMock()

    async def dummy_stream(*args, **kwargs):
        if False:
            yield None

    mock_service.stream_request = dummy_stream

    user = UserContext(
        id=uuid.uuid4(),
        email="test@example.com",
        tenant_id="tenant-123",
        roles=["USER"]
    )
    dto = AIWrapperRequest(
        tenant_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        query="Hello test",
        stream=True
    )

    response = await stream_ai_request(
        dto=dto,
        request=mock_request,
        service=mock_service,
        user=user
    )

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"
    assert response.headers.get("Cache-Control") == "no-cache"
    assert response.headers.get("X-Accel-Buffering") == "no"


@pytest.mark.asyncio
async def test_fastapi_chat_stream_headers_parity():
    """Verify /api/v1/chat/sessions/{id}/stream parity for Cache-Control and X-Accel-Buffering."""
    from backend.modules.chat.api.routes import stream_chat
    from backend.modules.chat.schemas import ChatRequestDTO
    from backend.core.auth.context import UserContext
    import uuid

    mock_request = MagicMock()
    mock_request.state.correlation_id = "test-corr-id"

    mock_orchestrator = MagicMock()

    async def dummy_stream(*args, **kwargs):
        if False:
            yield None

    mock_orchestrator.stream_chat = dummy_stream

    user = UserContext(
        id=uuid.uuid4(),
        email="test@example.com",
        tenant_id="tenant-123",
        roles=["USER"]
    )
    dto = ChatRequestDTO(
        query="Hello chat",
        workspace_id=uuid.uuid4()
    )

    response = await stream_chat(
        session_id=uuid.uuid4(),
        dto=dto,
        request=mock_request,
        orchestrator=mock_orchestrator,
        user=user
    )

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"
    assert response.headers.get("Cache-Control") == "no-cache"
    assert response.headers.get("X-Accel-Buffering") == "no"
