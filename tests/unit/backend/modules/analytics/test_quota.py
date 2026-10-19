from unittest.mock import AsyncMock, patch
import pytest

from backend.modules.analytics.schemas.errors import QuotaExceededError
from backend.modules.analytics.services.quota import QuotaGovernor


@pytest.mark.asyncio
async def test_quota_governor():
    mock_redis = AsyncMock()
    redis_store = {"quota:tokens:t1": 100000}

    async def mock_get(key):
        return redis_store.get(key)

    async def mock_set(key, val, ex=None):
        redis_store[key] = val

    async def mock_incrby(key, val):
        redis_store[key] = redis_store.get(key, 0) + val

    mock_redis.get.side_effect = mock_get
    mock_redis.set.side_effect = mock_set
    mock_redis.incrby.side_effect = mock_incrby

    with patch("backend.modules.analytics.services.quota.get_redis_client", return_value=mock_redis):
        gov = QuotaGovernor()

        assert await gov.check_and_reserve("t1", 50000) is True

        with pytest.raises(QuotaExceededError):
            await gov.check_and_reserve("t1", 150000)

        await gov.adjust_reservation_diff("t1", 10000)
        assert redis_store["quota:tokens:t1"] == 110000
