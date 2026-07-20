import pytest
from backend.modules.analytics.services.quota import QuotaGovernor
from backend.modules.analytics.schemas.errors import QuotaExceededError

@pytest.mark.asyncio
async def test_quota_governor():
    gov = QuotaGovernor()
    # t1 starts with 100,000 mock quota
    
    assert await gov.check_and_reserve("t1", 50000) is True
    assert gov._mock_redis["quota:tokens:t1"] == 50000
    
    with pytest.raises(QuotaExceededError):
        await gov.check_and_reserve("t1", 60000)
        
    await gov.adjust_reservation_diff("t1", 10000)
    assert gov._mock_redis["quota:tokens:t1"] == 60000
