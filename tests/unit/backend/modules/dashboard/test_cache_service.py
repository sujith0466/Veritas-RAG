import pytest

from backend.modules.dashboard.services.cache_service import RedisDashboardCache


@pytest.mark.asyncio
async def test_cache_service():
    cache = RedisDashboardCache()
    await cache.set("test_key", {"data": 123})
    val = await cache.get("test_key")
    assert val == {"data": 123}

    missing = await cache.get("wrong_key")
    assert missing is None
