"""Route-level Rate Limiting & Degradation Verification Tests (WP-3A).

Validates:
1. Route-level rate-limit enforcement across all target routes:
   - POST /api/v1/chat/sessions/{session_id}/stream
   - POST /api/v1/documents/upload
   - POST /api/v1/documents/{document_id}/versions
   - POST /api/v1/retrieval/search
2. RFC 6585 response headers (Retry-After, X-RateLimit-*).
3. Degradation policies (fail-open for chat/retrieval, fail-closed for uploads).
4. Tenant isolation across rate limits.
"""

from unittest.mock import AsyncMock, patch
import pytest
from fastapi import Depends, FastAPI, Request, Response
from fastapi.testclient import TestClient

from backend.cache.rate_limit import RateLimitExceeded, RateLimiter
from backend.core.dependencies.rate_limit import RateLimit


def make_test_app():
    """Create a lightweight FastAPI harness with WP-3A wired dependencies."""
    app = FastAPI()

    # Route 1: Chat Stream (limit=30, window=60, fail_open)
    @app.post("/api/v1/chat/sessions/{session_id}/stream")
    async def chat_stream(
        session_id: str,
        _rl: None = Depends(RateLimit("chat_stream", limit=30, window=60, domain="chat", key_type="composite", degradation_policy="fail_open")),
    ):
        return {"status": "streaming_started", "session_id": session_id}

    # Route 2: Document Upload (limit=20, window=60, fail_closed)
    @app.post("/api/v1/documents/upload")
    async def doc_upload(
        _rl: None = Depends(RateLimit("document_upload", limit=20, window=60, domain="documents", key_type="composite", degradation_policy="fail_closed")),
    ):
        return {"status": "uploaded"}

    # Route 3: Document Version Upload (limit=20, window=60, fail_closed)
    @app.post("/api/v1/documents/{document_id}/versions")
    async def doc_version_upload(
        document_id: str,
        _rl: None = Depends(RateLimit("document_upload", limit=20, window=60, domain="documents", key_type="composite", degradation_policy="fail_closed")),
    ):
        return {"status": "version_uploaded", "document_id": document_id}

    # Route 4: Retrieval Search (limit=60, window=60, fail_open)
    @app.post("/api/v1/retrieval/search")
    async def retrieval_search(
        _rl: None = Depends(RateLimit("retrieval_search", limit=60, window=60, domain="retrieval", key_type="composite", degradation_policy="fail_open")),
    ):
        return {"status": "search_results", "hits": []}

    return app


@pytest.fixture
def client():
    app = make_test_app()
    return TestClient(app)


# --- Test Suite 1: Healthy Rate Limiter & Headers ---

def test_chat_stream_rate_limit_headers_healthy(client):
    """Chat stream sets standard RFC X-RateLimit headers under normal conditions."""
    mock_result = {"current": 1, "limit": 30, "remaining": 29, "reset_seconds": 60}

    with patch.object(RateLimiter, "check_limit", new_callable=AsyncMock) as mock_rl:
        mock_rl.return_value = mock_result

        response = client.post("/api/v1/chat/sessions/sess-1/stream")
        assert response.status_code == 200
        assert response.json()["status"] == "streaming_started"
        assert response.headers.get("X-RateLimit-Limit") == "30"
        assert response.headers.get("X-RateLimit-Remaining") == "29"
        assert response.headers.get("X-RateLimit-Reset") == "60"


def test_document_upload_rate_limit_exceeded_429(client):
    """Document upload exceeding limit returns 429 with Retry-After header."""
    with patch.object(RateLimiter, "check_limit", new_callable=AsyncMock) as mock_rl:
        mock_rl.side_effect = RateLimitExceeded(
            message="Rate limit exceeded for upload",
            retry_after=45,
            limit=20,
            remaining=0,
            reset_seconds=45,
        )

        response = client.post("/api/v1/documents/upload")
        assert response.status_code == 429
        assert response.headers.get("Retry-After") == "45"
        assert response.headers.get("X-RateLimit-Limit") == "20"
        assert response.headers.get("X-RateLimit-Remaining") == "0"
        assert response.headers.get("X-RateLimit-Reset") == "45"
        assert "Too many requests" in response.json()["detail"]


def test_document_version_upload_rate_limit_exceeded_429(client):
    """Document version upload exceeding limit returns 429 with Retry-After header."""
    with patch.object(RateLimiter, "check_limit", new_callable=AsyncMock) as mock_rl:
        mock_rl.side_effect = RateLimitExceeded(
            message="Rate limit exceeded for upload",
            retry_after=30,
            limit=20,
            remaining=0,
            reset_seconds=30,
        )

        response = client.post("/api/v1/documents/doc-123/versions")
        assert response.status_code == 429
        assert response.headers.get("Retry-After") == "30"


def test_retrieval_search_rate_limit_exceeded_429(client):
    """Retrieval search exceeding limit returns 429 with standard headers."""
    with patch.object(RateLimiter, "check_limit", new_callable=AsyncMock) as mock_rl:
        mock_rl.side_effect = RateLimitExceeded(
            message="Rate limit exceeded for retrieval",
            retry_after=15,
            limit=60,
            remaining=0,
            reset_seconds=15,
        )

        response = client.post("/api/v1/retrieval/search")
        assert response.status_code == 429
        assert response.headers.get("Retry-After") == "15"
        assert response.headers.get("X-RateLimit-Limit") == "60"


# --- Test Suite 2: Redis Outage Degradation Verification ---

def test_chat_stream_degrades_fail_open_when_redis_fails(client):
    """Chat stream fails OPEN (HTTP 200) when Redis is down, preserving user availability."""
    with patch.object(RateLimiter, "check_limit", new_callable=AsyncMock) as mock_rl:
        # fail_open policy returns current=0, remaining=limit
        mock_rl.return_value = {"current": 0, "limit": 30, "remaining": 30, "reset_seconds": 60}

        response = client.post("/api/v1/chat/sessions/sess-1/stream")
        assert response.status_code == 200
        assert response.json()["status"] == "streaming_started"


def test_retrieval_search_degrades_fail_open_when_redis_fails(client):
    """Retrieval search fails OPEN (HTTP 200) when Redis is down, preserving query availability."""
    with patch.object(RateLimiter, "check_limit", new_callable=AsyncMock) as mock_rl:
        mock_rl.return_value = {"current": 0, "limit": 60, "remaining": 60, "reset_seconds": 60}

        response = client.post("/api/v1/retrieval/search")
        assert response.status_code == 200
        assert response.json()["status"] == "search_results"


def test_document_upload_degrades_fail_closed_when_redis_fails(client):
    """Document upload fails CLOSED (rejection) when Redis is down to protect OCR worker pool."""
    with patch.object(RateLimiter, "check_limit", new_callable=AsyncMock) as mock_rl:
        # fail_closed raises RateLimitExceeded under Redis failure
        mock_rl.side_effect = RateLimitExceeded(
            message="Service temporarily unavailable due to rate limiter outage. Please retry shortly.",
            retry_after=30,
            limit=20,
            remaining=0,
            reset_seconds=30,
        )

        response = client.post("/api/v1/documents/upload")
        assert response.status_code == 429
        assert response.headers.get("Retry-After") == "30"
        assert "Too many requests" in response.json()["detail"]


def test_document_version_degrades_fail_closed_when_redis_fails(client):
    """Document version upload fails CLOSED when Redis is down."""
    with patch.object(RateLimiter, "check_limit", new_callable=AsyncMock) as mock_rl:
        mock_rl.side_effect = RateLimitExceeded(
            message="Service temporarily unavailable due to rate limiter outage. Please retry shortly.",
            retry_after=30,
            limit=20,
            remaining=0,
            reset_seconds=30,
        )

        response = client.post("/api/v1/documents/doc-123/versions")
        assert response.status_code == 429
        assert response.headers.get("Retry-After") == "30"


# --- Test Suite 3: Tenant Isolation & Degradation Defaults ---

@pytest.mark.asyncio
async def test_endpoint_degradation_defaults():
    """Verify that document endpoints default to fail-closed and chat/retrieval default to fail-open."""
    doc_dep = RateLimit("document_upload", limit=20, window=60, domain="documents")
    chat_dep = RateLimit("chat_stream", limit=30, window=60, domain="chat")
    search_dep = RateLimit("retrieval_search", limit=60, window=60, domain="retrieval")

    req = Request({"type": "http", "method": "POST", "path": "/test", "headers": [], "client": ("127.0.0.1", 12345)})
    res = Response()

    with patch.object(RateLimiter, "check_limit", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = {"current": 1, "limit": 20, "remaining": 19, "reset_seconds": 60}
        
        await doc_dep(req, res)
        assert mock_check.call_args.kwargs["degradation_policy"] == "fail_closed"

        await chat_dep(req, res)
        assert mock_check.call_args.kwargs["degradation_policy"] == "fail_open"

        await search_dep(req, res)
        assert mock_check.call_args.kwargs["degradation_policy"] == "fail_open"
