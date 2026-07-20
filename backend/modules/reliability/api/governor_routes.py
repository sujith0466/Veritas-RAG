from fastapi import APIRouter
from backend.modules.reliability.schemas.reliability_dto import SelfHealingPolicyDTO, HealingActionDTO, SelfHealingPolicyUpdateDTO

router = APIRouter(prefix="/reliability/v1/governor", tags=["Governor"])

@router.get("/policies", response_model=SelfHealingPolicyDTO)
async def get_policy(tenant_id: str):
    return SelfHealingPolicyDTO(id="1", tenant_id=tenant_id)

@router.put("/policies", response_model=SelfHealingPolicyDTO)
async def update_policy(req: SelfHealingPolicyUpdateDTO):
    return SelfHealingPolicyDTO(id="1", tenant_id="t1")

@router.get("/actions", response_model=list[HealingActionDTO])
async def list_actions():
    return []

@router.post("/actions/{action_id}/rollback", response_model=HealingActionDTO)
async def rollback_action(action_id: str):
    return HealingActionDTO(id=action_id, tenant_id="t1", action_type="MOCK", trigger_reason="MOCK", changes_applied={}, is_rolled_back=True, executed_at="2026-07-20")
