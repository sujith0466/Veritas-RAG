"""Unit tests for SSEConcurrencyLimiterMiddleware."""

import asyncio
import pytest
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from backend.core.middleware.concurrency import SSEConcurrencyLimiterMiddleware


def create_request(path: str, accept: str = "") -> Request:
    headers = []
    if accept:
        headers.append((b"accept", accept.encode("latin-1")))

    scope = {
        "type": "http",
        "method": "POST",
        "path": path,
        "headers": headers,
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_non_sse_request_bypasses_limiter():
    async def dummy_app(scope, receive, send):
        pass

    middleware = SSEConcurrencyLimiterMiddleware(dummy_app, max_concurrent_streams=1)

    req = create_request(path="/api/v1/auth/login")

    async def call_next(request: Request):
        return PlainTextResponse("ok")

    response = await middleware.dispatch(req, call_next)
    assert response.status_code == 200
    assert middleware.active_streams == 0


@pytest.mark.asyncio
async def test_sse_request_under_limit_succeeds():
    async def dummy_app(scope, receive, send):
        pass

    middleware = SSEConcurrencyLimiterMiddleware(dummy_app, max_concurrent_streams=2)
    req = create_request(path="/api/v1/chat/sessions/123/stream")

    async def call_next(request: Request):
        # Verify active count is incremented during handling
        assert middleware.active_streams == 1
        return PlainTextResponse("stream ok")

    response = await middleware.dispatch(req, call_next)
    assert response.status_code == 200
    assert middleware.active_streams == 0


@pytest.mark.asyncio
async def test_sse_request_over_limit_returns_503():
    async def dummy_app(scope, receive, send):
        pass

    # Limit set to 1
    middleware = SSEConcurrencyLimiterMiddleware(dummy_app, max_concurrent_streams=1)

    # Manually hold a connection slot
    middleware._active_streams = 1

    req = create_request(path="/api/v1/chat/sessions/123/stream")

    async def call_next(request: Request):
        return PlainTextResponse("should not be reached")

    response = await middleware.dispatch(req, call_next)
    assert response.status_code == 503
    assert response.headers.get("retry-after") == "5"
    assert b"Too many concurrent streaming connections" in response.body


@pytest.mark.asyncio
async def test_sse_exception_releases_active_stream_counter():
    """Unhandled exceptions during stream execution must release the active counter in finally block."""
    async def dummy_app(scope, receive, send):
        pass

    middleware = SSEConcurrencyLimiterMiddleware(dummy_app, max_concurrent_streams=2)
    req = create_request(path="/api/v1/chat/sessions/123/stream")

    async def call_next_raising(request: Request):
        assert middleware.active_streams == 1
        raise RuntimeError("Simulated pipeline failure during streaming")

    with pytest.raises(RuntimeError, match="Simulated pipeline failure"):
        await middleware.dispatch(req, call_next_raising)

    assert middleware.active_streams == 0


@pytest.mark.asyncio
async def test_sse_client_disconnect_releases_active_stream_counter():
    """Client disconnects (asyncio.CancelledError) must release the active counter in finally block."""
    async def dummy_app(scope, receive, send):
        pass

    middleware = SSEConcurrencyLimiterMiddleware(dummy_app, max_concurrent_streams=2)
    req = create_request(path="/api/v1/chat/sessions/123/stream")

    async def call_next_cancelled(request: Request):
        assert middleware.active_streams == 1
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await middleware.dispatch(req, call_next_cancelled)

    assert middleware.active_streams == 0
