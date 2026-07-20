import pytest
from backend.modules.reliability.services.tuner import AdaptiveParameterTuner

@pytest.mark.asyncio
async def test_tuner():
    tuner = AdaptiveParameterTuner()
    overrides = await tuner.apply_tuning("t1", "LOW_RECALL")
    assert overrides.retrieval_top_k == 10
    assert overrides.similarity_threshold == 0.68
    
    active = await tuner.get_active_overrides("t1")
    assert active.retrieval_top_k == 10
