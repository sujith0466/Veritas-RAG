import pytest

from backend.core.resilience.failover import FailoverOrchestrator
from backend.core.resilience.region_router import RegionRouter


@pytest.mark.asyncio
async def test_failover():
    router = RegionRouter()
    orch = FailoverOrchestrator(router)

    assert router.route_request() == "us-east-1"

    await orch.trigger_failover("eu-west-1")
    assert router.route_request() == "eu-west-1"
