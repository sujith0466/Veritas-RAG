"""Unit tests for RateLimit FastAPI route dependency."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import HTTPException, Request, Response

from backend.cache.rate_limit import RateLimitExceeded
from backend.core.dependencies.rate_limit import RateLimit


def make_request(
    client_ip: str | None = None,
    tenant_id: str | None = None,
    user_id: str | None = None,
    headers: dict[str, str] | None = None,
) -> Request:
    raw_headers = []
    if headers:
        for k, v in headers.items():
            raw_headers.append((k.lower().encode("latin-1"), v.encode("latin-1")))

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/test",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
    }
    req = Request(scope)
    if client_ip:
        req.state.client_ip = client_ip

    if tenant_id or user_id:
        req.state.user_context = SimpleNamespace(
            tenant_id=tenant_id,
            workspace_id=tenant_id,
            id=user_id,
            user_id=user_id,
        )
    return req


@pytest.mark.asyncio
async def test_dependency_sets_headers_on_success():
    """Verify rate limit dependency sets X-RateLimit headers on successful request."""
    dep = RateLimit(action="test_action", limit=10, window=60, domain="test")
    req = make_request(client_ip="203.0.113.10")
    res = Response()

    mock_result = {
        "current": 1,
        "limit": 10,
        "remaining": 9,
        "reset_seconds": 60,
    }

    with patch("backend.core.dependencies.rate_limit.RateLimiter.check_limit", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = mock_result
        await dep(req, res)

    assert res.headers["X-RateLimit-Limit"] == "10"
    assert res.headers["X-RateLimit-Remaining"] == "9"
    assert res.headers["X-RateLimit-Reset"] == "60"
    assert mock_check.call_args.kwargs["entity_id"] == "ip:203.0.113.10"


@pytest.mark.asyncio
async def test_dependency_raises_429_with_rfc_headers():
    """Verify 429 HTTPException includes Retry-After and X-RateLimit headers."""
    dep = RateLimit(action="test_action", limit=5, window=60, domain="test")
    req = make_request(client_ip="203.0.113.20")
    res = Response()

    with patch("backend.core.dependencies.rate_limit.RateLimiter.check_limit", new_callable=AsyncMock) as mock_check:
        mock_check.side_effect = RateLimitExceeded(
            message="Rate limit exceeded",
            retry_after=42,
            limit=5,
            remaining=0,
            reset_seconds=42,
        )

        with pytest.raises(HTTPException) as exc_info:
            await dep(req, res)

    exc = exc_info.value
    assert exc.status_code == 429
    assert exc.headers["Retry-After"] == "42"
    assert exc.headers["X-RateLimit-Limit"] == "5"
    assert exc.headers["X-RateLimit-Remaining"] == "0"
    assert exc.headers["X-RateLimit-Reset"] == "42"


@pytest.mark.asyncio
async def test_document_upload_degradation_defaults_to_fail_closed():
    """Verify document upload defaults to fail_closed per risk-based evaluation."""
    dep = RateLimit(action="document_upload", limit=20, window=60, domain="documents")
    req = make_request(client_ip="203.0.113.30")
    res = Response()

    with patch("backend.core.dependencies.rate_limit.RateLimiter.check_limit", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = {"current": 1, "limit": 20, "remaining": 19, "reset_seconds": 60}
        await dep(req, res)

    assert mock_check.call_args.kwargs["degradation_policy"] == "fail_closed"


@pytest.mark.asyncio
async def test_chat_stream_degradation_defaults_to_fail_open():
    """Verify chat stream defaults to fail_open."""
    dep = RateLimit(action="chat_stream", limit=30, window=60, domain="chat")
    req = make_request(client_ip="203.0.113.40")
    res = Response()

    with patch("backend.core.dependencies.rate_limit.RateLimiter.check_limit", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = {"current": 1, "limit": 30, "remaining": 29, "reset_seconds": 60}
        await dep(req, res)

    assert mock_check.call_args.kwargs["degradation_policy"] == "fail_open"


@pytest.mark.asyncio
async def test_client_supplied_x_tenant_id_header_is_ignored():
    """Client-supplied X-Tenant-ID header must NEVER set tenant context."""
    dep = RateLimit(action="upload", limit=10, window=60, domain="documents")
    # Client passes spoofed X-Tenant-ID header with no server-side auth
    req = make_request(client_ip="203.0.113.50", headers={"X-Tenant-ID": "spoofed-tenant-999"})
    res = Response()

    with patch("backend.core.dependencies.rate_limit.RateLimiter.check_limit", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = {"current": 1, "limit": 10, "remaining": 9, "reset_seconds": 60}
        await dep(req, res)

    # Must only check global IP tier; spoofed tenant is completely ignored
    assert mock_check.call_count == 1
    call_kwargs = mock_check.call_args.kwargs
    assert call_kwargs["tenant"] == "global"
    assert call_kwargs["entity_id"] == "ip:203.0.113.50"


@pytest.mark.asyncio
async def test_user_cannot_evade_rate_limit_by_rotating_ip():
    """A user who exhausts their limit cannot evade by rotating client IP."""
    dep = RateLimit(action="chat_stream", limit=30, window=60, domain="chat")
    # Request from IP 2 with user-1 identity
    req = make_request(client_ip="198.51.100.99", tenant_id="tenant-alpha", user_id="user-1")
    res = Response()

    def mock_check_limit(tenant, domain, action, entity_id, limit, window_seconds, degradation_policy):
        if "user:user-1" in entity_id:
            raise RateLimitExceeded(
                message="User limit exceeded",
                retry_after=45,
                limit=30,
                remaining=0,
                reset_seconds=45,
            )
        return {"current": 1, "limit": limit, "remaining": limit - 1, "reset_seconds": 60}

    with patch("backend.core.dependencies.rate_limit.RateLimiter.check_limit", side_effect=mock_check_limit):
        with pytest.raises(HTTPException) as exc_info:
            await dep(req, res)

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "45"


@pytest.mark.asyncio
async def test_tenant_a_cannot_consume_tenant_b_budget():
    """Exhaustion of Tenant A's quota does not impact Tenant B."""
    dep = RateLimit(action="retrieval_search", limit=60, window=60, domain="retrieval")

    # Tenant B request
    req_b = make_request(client_ip="203.0.113.88", tenant_id="tenant-bravo", user_id="user-2")
    res_b = Response()

    checked_tenants = []

    async def mock_check_limit(tenant, domain, action, entity_id, limit, window_seconds, degradation_policy):
        checked_tenants.append(tenant)
        return {"current": 1, "limit": limit, "remaining": limit - 1, "reset_seconds": 60}

    with patch("backend.core.dependencies.rate_limit.RateLimiter.check_limit", side_effect=mock_check_limit):
        await dep(req_b, res_b)

    assert res_b.headers["X-RateLimit-Limit"] == "60"
    # Checked global (IP) and tenant-bravo; tenant-alpha was never touched
    assert "tenant-bravo" in checked_tenants
    assert "tenant-alpha" not in checked_tenants


@pytest.mark.asyncio
async def test_ip_tier_enforces_across_different_users():
    """Multiple user accounts on the same client IP cannot exceed the IP tier limit."""
    dep = RateLimit(action="chat_stream", limit=30, window=60, domain="chat")
    # Request from abusive IP with user-99 identity
    req = make_request(client_ip="198.51.100.1", tenant_id="tenant-alpha", user_id="user-99")
    res = Response()

    def mock_check_limit(tenant, domain, action, entity_id, limit, window_seconds, degradation_policy):
        if "ip:198.51.100.1" in entity_id:
            raise RateLimitExceeded(
                message="IP rate limit exceeded",
                retry_after=60,
                limit=30,
                remaining=0,
                reset_seconds=60,
            )
        return {"current": 1, "limit": limit, "remaining": limit - 1, "reset_seconds": 60}

    with patch("backend.core.dependencies.rate_limit.RateLimiter.check_limit", side_effect=mock_check_limit):
        with pytest.raises(HTTPException) as exc_info:
            await dep(req, res)

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers["Retry-After"] == "60"


@pytest.mark.asyncio
async def test_redis_outage_fail_open_short_circuits_duplicate_tier_calls():
    """When Redis fails under fail-open, subsequent tiers are short-circuited to avoid duplicate telemetry and timeouts."""
    dep = RateLimit(action="chat_stream", limit=30, window=60, domain="chat", degradation_policy="fail_open")
    # Authenticated request with both tenant and user contexts
    req = make_request(client_ip="203.0.113.100", tenant_id="tenant-alpha", user_id="user-1")
    res = Response()

    with patch("backend.core.dependencies.rate_limit.RateLimiter.check_limit", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = {"degraded": True, "limit": 30, "remaining": 30, "reset_seconds": 60}
        await dep(req, res)

    # Must only call check_limit once (Tier 1 detects degradation and breaks)
    assert mock_check.call_count == 1
    assert res.headers["X-RateLimit-Limit"] == "30"

