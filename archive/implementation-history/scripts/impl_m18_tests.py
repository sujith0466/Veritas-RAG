import os
import sys
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 18.4 Implementation (Tests)...")
    os.makedirs("tests/unit/backend/modules/reliability", exist_ok=True)
    os.makedirs("tests/integration", exist_ok=True)
    
    # 1. test_tuner.py
    with open("tests/unit/backend/modules/reliability/test_tuner.py", "w") as f:
        f.write("""import pytest
from backend.modules.reliability.services.tuner import AdaptiveParameterTuner

@pytest.mark.asyncio
async def test_tuner():
    tuner = AdaptiveParameterTuner()
    overrides = await tuner.apply_tuning("t1", "LOW_RECALL")
    assert overrides.retrieval_top_k == 10
    assert overrides.similarity_threshold == 0.68
    
    active = await tuner.get_active_overrides("t1")
    assert active.retrieval_top_k == 10
""")

    # 2. test_model_rotation.py
    with open("tests/unit/backend/modules/reliability/test_model_rotation.py", "w") as f:
        f.write("""import pytest
from backend.modules.reliability.fallbacks.model_rotation import ModelRotationOrchestrator

@pytest.mark.asyncio
async def test_model_rotation():
    orch = ModelRotationOrchestrator()
    new_provider = await orch.rotate_provider("t1", "azure-openai")
    assert new_provider == "anthropic"
""")

    # 3. test_governor.py
    with open("tests/unit/backend/modules/reliability/test_governor.py", "w") as f:
        f.write("""import pytest
from backend.modules.reliability.services.governor import SelfHealingGovernor
from backend.modules.reliability.services.tuner import AdaptiveParameterTuner
from backend.modules.reliability.fallbacks.model_rotation import ModelRotationOrchestrator
from backend.modules.reliability.repositories.governor_repository import GovernorRepository
from backend.modules.reliability.models.self_healing_policy import SelfHealingPolicyORM

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
""")

    print("Created test files.")
    
    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/backend/modules/reliability/test_tuner.py", "tests/unit/backend/modules/reliability/test_model_rotation.py", "tests/unit/backend/modules/reliability/test_governor.py"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    print("Milestone 18.4 completed.")

if __name__ == "__main__":
    main()
