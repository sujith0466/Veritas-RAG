import uuid

from fastapi import APIRouter

from backend.modules.alerts.schemas.alert_dto import (AlertHistoryDTO,
                                                      AlertRuleCreateDTO,
                                                      AlertRuleDTO)

router = APIRouter(prefix="/alerts/v1", tags=["Alerts"])


@router.post("/rules", response_model=AlertRuleDTO)
async def create_rule(req: AlertRuleCreateDTO):
    return AlertRuleDTO(id=str(uuid.uuid4()), tenant_id="tenant_1", **req.model_dump())


@router.get("/rules", response_model=list[AlertRuleDTO])
async def list_rules(tenant_id: str):
    return []


@router.get("/history", response_model=list[AlertHistoryDTO])
async def list_history():
    return []
