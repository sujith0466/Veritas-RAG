from fastapi import APIRouter

from backend.modules.security.schemas.security_dto import AuditEventDTO

router = APIRouter(prefix="/security/v1", tags=["Security"])


@router.get("/audit/{tenant_id}", response_model=list[AuditEventDTO])
async def get_audit_logs(tenant_id: str):
    return [
        AuditEventDTO(
            tenant_id=tenant_id,
            actor_id="admin-123",
            action="API_KEY_ROTATED",
            resource="provider:openai",
            status="SUCCESS",
            timestamp="2026-07-20T12:00:00Z",
        )
    ]
