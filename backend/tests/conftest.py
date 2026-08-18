"""Global test fixtures and configuration for RAGuard test suites."""

import pytest
from backend.cache.client import get_redis_client


@pytest.fixture(autouse=True)
async def reset_rate_limits():
    """Ensure deterministic rate-limit state across tests without modifying production limits."""
    redis = get_redis_client()
    if redis:
        try:
            await redis.flushdb()
        except Exception:
            pass
    yield
