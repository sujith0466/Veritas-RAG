import pytest

from backend.modules.reliability.fallbacks.model_rotation import ModelRotationOrchestrator
from backend.modules.reliability.models.self_healing_policy import SelfHealingPolicyORM
from backend.modules.reliability.services.governor import SelfHealingGovernor
from backend.modules.reliability.services.tuner import AdaptiveParameterTuner


class MockRepo:
    async def get_policy(self, tenant_id: str):
        return SelfHealingPolicyORM(tenant_id=tenant_id, auto_model_rotation=True, auto_parameter_tuning=True, max_interventions_per_hour=10)
    async def save_action_log(self, log):
        return log

@pytest.mark.asyncio
async def test_governor():
    tuner = AdaptiveParameterTuner()
    orch = ModelRotationOrchestrator()
    repo = MockRepo()
    # Ignoring type errors in test setup for MockRepo
    gov = SelfHealingGovernor(tuner, orch, repo)  # type: ignore

    await gov.on_circuit_breaker_tripped("t1", "azure-openai")
    assert gov._intervention_count == 1

    await gov.on_score_drop("t1", "LOW_RECALL")
    assert gov._intervention_count == 2
