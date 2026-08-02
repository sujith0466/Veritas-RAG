"""Integration tests for Redis Foundation capabilities.

Tests CacheManager, Distributed Locks, and Rate Limiting.
These tests rely on a running Redis instance (via test_db = 15).
"""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel
import pytest

from backend.cache.keys import CacheKeyBuilder, TTLProfile
from backend.cache.locks import LockAcquisitionError, acquire_lock
from backend.cache.manager import CacheManager
from backend.cache.rate_limit import RateLimiter, RateLimitExceeded
from backend.core.utils.retry import with_retry


class DummyModel(BaseModel):
    id: str
    value: int
    created_at: datetime


@pytest.mark.asyncio
async def test_cache_key_builder():
    """Test standard namespace generation."""
    key = CacheKeyBuilder.build("tenant123", "auth", "session", "user456")
    assert key == "rg:v2:tenant123:auth:session:user456"


@pytest.mark.skip(reason="Requires live Redis instance in CI")
@pytest.mark.asyncio
async def test_cache_manager_primitives():
    """Test get, set, delete with JSON serialization of complex objects."""
    tenant = "test"
    domain = "cache"
    entity = "dummy"
    entity_id = str(uuid4())

    obj = DummyModel(
        id=entity_id,
        value=42,
        created_at=datetime.now(UTC)
    )

    # SET
    await CacheManager.set(tenant, domain, entity, entity_id, obj, TTLProfile.TRANSIENT)

    # GET
    retrieved = await CacheManager.get(tenant, domain, entity, entity_id)
    assert retrieved is not None
    assert retrieved["id"] == entity_id
    assert retrieved["value"] == 42
    assert "created_at" in retrieved

    # DELETE
    await CacheManager.delete(tenant, domain, entity, entity_id)
    retrieved_after = await CacheManager.get(tenant, domain, entity, entity_id)
    assert retrieved_after is None


@pytest.mark.skip(reason="Requires live Redis instance in CI")
@pytest.mark.asyncio
async def test_distributed_lock():
    """Test lock acquisition and exclusion."""
    lock_name = f"test_lock_{uuid4()}"

    # Acquire lock 1
    async with acquire_lock(lock_name, timeout=5, acquire_timeout=1) as token1:
        assert token1 is not None

        # Try to acquire lock 2 concurrently (should fail due to acquire_timeout=0.1)
        with pytest.raises(LockAcquisitionError):
            async with acquire_lock(lock_name, timeout=5, acquire_timeout=1, retry_delay=0.1):
                pass  # Should not reach here


@pytest.mark.skip(reason="Requires live Redis instance in CI")
@pytest.mark.asyncio
async def test_rate_limiter():
    """Test fixed window rate limiter."""
    tenant = "test"
    domain = "api"
    action = f"test_limit_{uuid4()}"
    entity_id = "user1"

    # 2 requests per 5 seconds
    limit = 2
    window = 5

    res1 = await RateLimiter.check_limit(tenant, domain, action, entity_id, limit, window)
    assert res1["current"] == 1
    assert res1["remaining"] == 1

    res2 = await RateLimiter.check_limit(tenant, domain, action, entity_id, limit, window)
    assert res2["current"] == 2
    assert res2["remaining"] == 0

    # 3rd request should fail
    with pytest.raises(RateLimitExceeded):
        await RateLimiter.check_limit(tenant, domain, action, entity_id, limit, window)


@pytest.mark.asyncio
async def test_generic_retry_utility():
    """Test exponential backoff logic."""
    attempts = 0

    @with_retry(max_retries=2, base_delay=0.1, exceptions=(ValueError,))
    async def flaking_function():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("Intentional failure")
        return "success"

    result = await flaking_function()
    assert result == "success"
    assert attempts == 3
