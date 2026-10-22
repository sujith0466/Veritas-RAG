"""Unit tests for atomic sliding-window rate limiting."""

import time
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.cache.rate_limit import RateLimiter, RateLimitExceeded
from backend.ai.wrapper.rate_limit import RateLimiter as AIRateLimiter, RateLimitExceededError


@pytest.mark.asyncio
async def test_sliding_window_allows_requests_below_limit():
    """Verify check_limit allows requests under the configured threshold."""
    mock_redis = AsyncMock()
    # Mock Redis returning [allowed=1, remaining=4, retry_after=0]
    mock_redis.eval.return_value = [1, 4, 0]

    with patch("backend.cache.rate_limit.get_redis_client", return_value=mock_redis):
        result = await RateLimiter.check_limit(
            tenant="test_tenant",
            domain="chat",
            action="chat_stream",
            entity_id="192.168.1.100",
            limit=5,
            window_seconds=60,
        )

    assert result["current"] == 1
    assert result["limit"] == 5
    assert result["remaining"] == 4
    assert result["reset_seconds"] == 60


@pytest.mark.asyncio
async def test_sliding_window_blocks_and_raises_when_limit_exceeded():
    """Verify check_limit raises RateLimitExceeded with accurate retry_after."""
    mock_redis = AsyncMock()
    # Mock Redis returning [allowed=0, remaining=0, retry_after=23]
    mock_redis.eval.return_value = [0, 0, 23]

    with patch("backend.cache.rate_limit.get_redis_client", return_value=mock_redis):
        with pytest.raises(RateLimitExceeded) as exc_info:
            await RateLimiter.check_limit(
                tenant="test_tenant",
                domain="chat",
                action="chat_stream",
                entity_id="192.168.1.100",
                limit=5,
                window_seconds=60,
            )

    exc = exc_info.value
    assert exc.retry_after == 23
    assert exc.limit == 5
    assert exc.remaining == 0
    assert exc.reset_seconds == 23


@pytest.mark.asyncio
async def test_redis_failure_fail_open_degradation():
    """Verify Redis error results in fail_open when policy is fail_open."""
    mock_redis = AsyncMock()
    mock_redis.eval.side_effect = ConnectionError("Redis is unreachable")

    with patch("backend.cache.rate_limit.get_redis_client", return_value=mock_redis):
        result = await RateLimiter.check_limit(
            tenant="test_tenant",
            domain="chat",
            action="chat_stream",
            entity_id="192.168.1.100",
            limit=30,
            window_seconds=60,
            degradation_policy="fail_open",
        )

    assert result["degraded"] is True
    assert result["limit"] == 30
    assert result["remaining"] == 30


@pytest.mark.asyncio
async def test_redis_failure_fail_closed_degradation():
    """Verify Redis error raises RateLimitExceeded when policy is fail_closed."""
    mock_redis = AsyncMock()
    mock_redis.eval.side_effect = ConnectionError("Redis connection lost")

    with patch("backend.cache.rate_limit.get_redis_client", return_value=mock_redis):
        with pytest.raises(RateLimitExceeded) as exc_info:
            await RateLimiter.check_limit(
                tenant="test_tenant",
                domain="documents",
                action="document_upload",
                entity_id="192.168.1.100",
                limit=20,
                window_seconds=60,
                degradation_policy="fail_closed",
            )

    exc = exc_info.value
    assert exc.retry_after == 30
    assert "temporarily unavailable" in str(exc)


@pytest.mark.asyncio
async def test_redis_failure_emits_structured_high_severity_alert_and_metric():
    """Verify Redis failure logs high-severity alert and increments Prometheus metric."""
    mock_redis = AsyncMock()
    mock_redis.eval.side_effect = ConnectionError("Redis socket timeout")

    with patch("backend.cache.rate_limit.get_redis_client", return_value=mock_redis), \
         patch("backend.cache.rate_limit.logger") as mock_logger, \
         patch("backend.observability.metrics.prometheus.RATE_LIMIT_REDIS_FAILURES_TOTAL") as mock_metric:

        await RateLimiter.check_limit(
            tenant="test_tenant",
            domain="chat",
            action="chat_stream",
            entity_id="192.168.1.100",
            limit=30,
            window_seconds=60,
            degradation_policy="fail_open",
        )

        # 1. High-severity structured log emitted
        assert mock_logger.error.called
        log_kwargs = mock_logger.error.call_args.kwargs
        assert log_kwargs["severity"] == "HIGH"
        assert log_kwargs["action"] == "chat_stream"
        assert log_kwargs["policy"] == "fail_open"

        # 2. Prometheus metric incremented
        assert mock_metric.labels.called
        assert mock_metric.labels.return_value.inc.called


@pytest.mark.asyncio
async def test_redis_outage_recovery():
    """Verify recovery: once Redis reconnects, rate limiter resumes normal atomic operation."""
    mock_redis = AsyncMock()

    with patch("backend.cache.rate_limit.get_redis_client", return_value=mock_redis):
        # Step 1: Outage scenario (fails open)
        mock_redis.eval.side_effect = ConnectionError("Redis down")
        res_outage = await RateLimiter.check_limit(
            tenant="test_tenant",
            domain="chat",
            action="chat_stream",
            entity_id="192.168.1.100",
            limit=30,
            window_seconds=60,
            degradation_policy="fail_open",
        )
        assert res_outage["degraded"] is True

        # Step 2: Recovery scenario (connection restored)
        mock_redis.eval.side_effect = None
        mock_redis.eval.return_value = [1, 29, 0]
        res_recovered = await RateLimiter.check_limit(
            tenant="test_tenant",
            domain="chat",
            action="chat_stream",
            entity_id="192.168.1.100",
            limit=30,
            window_seconds=60,
            degradation_policy="fail_open",
        )
        assert res_recovered.get("degraded") is not True
        assert res_recovered["current"] == 1
        assert res_recovered["remaining"] == 29


@pytest.mark.asyncio
async def test_ai_wrapper_atomic_sliding_window_success():
    """Verify AI wrapper rate limiter checks and adds atomically."""
    ai_limiter = AIRateLimiter()
    mock_redis = AsyncMock()
    mock_redis.eval.return_value = [1, "ok", 0]
    ai_limiter.redis = mock_redis

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    await ai_limiter.check_rate_limit(tenant_id=tenant_id, user_id=user_id)
    assert mock_redis.eval.called


@pytest.mark.asyncio
async def test_ai_wrapper_atomic_sliding_window_tenant_exceeded():
    """Verify AI wrapper raises RateLimitExceededError when tenant limit exceeded."""
    ai_limiter = AIRateLimiter()
    mock_redis = AsyncMock()
    mock_redis.eval.return_value = [0, "tenant", 45]
    ai_limiter.redis = mock_redis

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    with pytest.raises(RateLimitExceededError) as exc_info:
        await ai_limiter.check_rate_limit(tenant_id=tenant_id, user_id=user_id)

    assert "Tenant request rate limit exceeded" in str(exc_info.value)
    assert exc_info.value.retry_after == 45
