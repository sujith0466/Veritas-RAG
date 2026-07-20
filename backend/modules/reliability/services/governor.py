from backend.modules.reliability.services.tuner import AdaptiveParameterTuner
from backend.modules.reliability.fallbacks.model_rotation import ModelRotationOrchestrator
from backend.modules.reliability.models.self_healing_policy import SelfHealingPolicyORM
from backend.modules.reliability.models.healing_action_log import HealingActionLogORM
from backend.modules.reliability.repositories.governor_repository import GovernorRepository
import uuid

class SelfHealingGovernor:
    def __init__(self, tuner: AdaptiveParameterTuner, orchestrator: ModelRotationOrchestrator, repo: GovernorRepository):
        self.tuner = tuner
        self.orchestrator = orchestrator
        self.repo = repo
        self._intervention_count = 0  # In-memory throttle mock

    async def on_circuit_breaker_tripped(self, tenant_id: str, provider: str):
        policy = await self.repo.get_policy(tenant_id)
        if not policy or not policy.auto_model_rotation:
            return
            
        if self._intervention_count >= policy.max_interventions_per_hour:
            return
            
        self._intervention_count += 1
        new_provider = await self.orchestrator.rotate_provider(tenant_id, provider)
        
        log = HealingActionLogORM(
            tenant_id=tenant_id,
            action_type="MODEL_ROTATION",
            trigger_reason=f"Circuit breaker tripped for {provider}",
            changes_applied={"new_provider": new_provider}
        )
        await self.repo.save_action_log(log)

    async def on_score_drop(self, tenant_id: str, diagnosis: str):
        policy = await self.repo.get_policy(tenant_id)
        if not policy or not policy.auto_parameter_tuning:
            return
            
        if self._intervention_count >= policy.max_interventions_per_hour:
            return
            
        self._intervention_count += 1
        overrides = await self.tuner.apply_tuning(tenant_id, diagnosis)
        
        log = HealingActionLogORM(
            tenant_id=tenant_id,
            action_type="PARAMETER_TUNE",
            trigger_reason=f"System degradation diagnosed as {diagnosis}",
            changes_applied=overrides.model_dump(exclude_none=True)
        )
        await self.repo.save_action_log(log)
