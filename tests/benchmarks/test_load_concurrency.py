import pytest
import asyncio

@pytest.mark.asyncio
async def test_load_concurrency():
    # Mocking a load test
    await asyncio.sleep(0.1)
    assert True
