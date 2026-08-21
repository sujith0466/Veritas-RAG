"""Compliance Security API Endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.core.auth.context import UserContext
from backend.core.dependencies.rbac import require_role
from backend.core.permissions.rbac import Role
from backend.modules.security.schemas.security_dto import AuditEventDTO

router = APIRouter(prefix="/security/v1", tags=["Security"])


@router.get(
    "/audit/{tenant_id}",
    response_model=list[AuditEventDTO],
    status_code=status.HTTP_200_OK,
    summary="Get compliance audit events",
)
async def get_audit_logs(
    tenant_id: str,
    auth: Annotated[UserContext, Depends(require_role(Role.PLATFORM_ADMIN))],
) -> list[AuditEventDTO]:
    """Retrieve compliance audit events (Platform Admin only)."""
    return []
