import pytest

from backend.core.chaos.injector import ChaosInjector
from backend.core.chaos.models.fault_policy import FaultPolicyORM


@pytest.mark.asyncio
async def test_chaos_injector():
    injector = ChaosInjector()
    injector.is_production = False

    policy = FaultPolicyORM(chaos_token="test-token", fault_type="LLM_HTTP_503", error_rate_pct=1.0, is_active=True)
    injector.seed_mock_policy("test-token", policy)

    with pytest.raises(Exception, match="503"):
        await injector.check_fault_injection("test-token")

    injector.is_production = True
    await injector.check_fault_injection("test-token") # Should not raise
