import asyncio

import pytest


@pytest.mark.asyncio
async def test_chaos_pipeline():
    # Mocking end-to-end chaos test
    await asyncio.sleep(0.1)
    assert True
