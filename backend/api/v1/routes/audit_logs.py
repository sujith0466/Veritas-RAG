from datetime import datetime
import math
from typing import Annotated
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from backend.api.v1.schemas.audit_log import AuditLogDTO
from backend.api.v1.schemas.common import PaginatedResponse, PaginationMetadata, ResponseMetadata
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
    request: Request,
    auth: Annotated[UserContext, Depends(require_role(Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN))],
    repo: Annotated[IAuditLogRepository, Depends(get_audit_log_repository)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    query: str | None = Query(None, description="Search term across action, resource, or user"),
    action: str | None = Query(None, description="Filter by action name"),
    start_date: datetime | None = Query(None, description="Filter logs on or after timestamp"),
    end_date: datetime | None = Query(None, description="Filter logs on or before timestamp"),
) -> PaginatedResponse[AuditLogDTO]:
    """Retrieve audit logs for the authenticated user's workspace with true pagination and search."""
    tenant_id_str = auth.tenant_id
    if not tenant_id_str:
        raise ValueError("Tenant ID is required in the user context to fetch audit logs.")

    tenant_id = UUID(tenant_id_str)
    skip = (page - 1) * page_size

    logs, total_count = await repo.search_logs(
        tenant_id=tenant_id,
        query=query,
        action=action,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=page_size,
    )

    items = [AuditLogDTO.model_validate(log) for log in logs]
    total_pages = max(1, math.ceil(total_count / page_size)) if total_count > 0 else 1
    req_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    return PaginatedResponse(
        items=items,
        pagination=PaginationMetadata(
            page=page,
            size=page_size,
            total_elements=total_count,
            total_pages=total_pages,
        ),
        metadata=ResponseMetadata(request_id=req_id),
    )
