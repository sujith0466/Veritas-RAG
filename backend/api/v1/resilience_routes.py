from fastapi import APIRouter
from backend.core.chaos.schemas.chaos_dto import FaultPolicyCreateDTO, FaultPolicyDTO, FailoverCommandDTO, FailoverStatusDTO

router = APIRouter(prefix="/resilience/v1", tags=["Resilience"])

@router.post("/chaos/policies", response_model=FaultPolicyDTO)
async def create_chaos_policy(req: FaultPolicyCreateDTO):
    return FaultPolicyDTO(id="1", expires_at="2026-07-21T00:00:00Z", **req.model_dump())

@router.post("/failover/trigger", response_model=FailoverStatusDTO)
async def trigger_failover(req: FailoverCommandDTO):
    return FailoverStatusDTO(status="SUCCESS", active_region=req.target_region, message="Failover complete")
