import pytest
from backend.modules.reliability.fallbacks.model_rotation import ModelRotationOrchestrator

@pytest.mark.asyncio
async def test_model_rotation():
    orch = ModelRotationOrchestrator()
    new_provider = await orch.rotate_provider("t1", "azure-openai")
    assert new_provider == "anthropic"
