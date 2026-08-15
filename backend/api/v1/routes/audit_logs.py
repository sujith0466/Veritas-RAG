"""Audit Logs API Endpoints (F12.6)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from backend.api.v1.schemas.audit_log import AuditLogDTO
from backend.api.v1.schemas.common import PaginatedResponse, ResponseMetadata
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_audit_log_repository
from backend.core.dependencies.rbac import require_role
from backend.core.permissions.rbac import Role
from backend.repositories.interfaces.audit_log_repository import IAuditLogRepository

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get(
    "",
    response_model=PaginatedResponse[AuditLogDTO],
    status_code=status.HTTP_200_OK,
    summary="List workspace audit logs",
)
async def list_audit_logs(
    auth: Annotated[UserContext, Depends(require_role(Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN))],
    repo: Annotated[IAuditLogRepository, Depends(get_audit_log_repository)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> PaginatedResponse[AuditLogDTO]:
    """Retrieve audit logs for the authenticated user's workspace."""
    # Ensure a tenant_id exists in the user context
    tenant_id_str = auth.tenant_id
    if not tenant_id_str:
        # Fallback or error if tenant_id is missing, but auth ensures it's present for workspace context
        raise ValueError("Tenant ID is required in the user context to fetch audit logs.")
    
    tenant_id = UUID(tenant_id_str)
    skip = (page - 1) * page_size
    
    logs = await repo.get_by_tenant_id(tenant_id=tenant_id, skip=skip, limit=page_size)
    # Note: total count requires a count query in repo, but for now we simulate it or add it later
    # To keep it simple, we'll return total as -1 or implement a count query if needed
    
    items = [AuditLogDTO.model_validate(log) for log in logs]
    
    return PaginatedResponse(
        data=items,
        total=len(items),  # Simplified: actual total requires a count query
        page=page,
        page_size=page_size,
        metadata=ResponseMetadata(),
    )
