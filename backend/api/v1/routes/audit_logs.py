from datetime import datetime
import math
from typing import Annotated
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.audit_log import AuditLogDTO
from backend.api.v1.schemas.common import PaginatedResponse, PaginationMetadata, ResponseMetadata
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_audit_log_repository, get_db
from backend.core.permissions.guards import record_diagnostic_access, validate_diagnostic_ticket
from backend.core.permissions.rbac import Role
from backend.repositories.interfaces.audit_log_repository import IAuditLogRepository

router = APIRouter(tags=["Audit Logs"])

CUSTOMER_AUDIT_PATHS = {"/api/v1/audit-logs", "/audit-logs", "/api/v1/audit/logs", "/audit/logs"}


@router.get(
    "/audit-logs",
    response_model=PaginatedResponse[AuditLogDTO],
    status_code=status.HTTP_200_OK,
    summary="List workspace audit logs",
)
@router.get(
    "/audit/logs",
    response_model=PaginatedResponse[AuditLogDTO],
    status_code=status.HTTP_200_OK,
    summary="List workspace audit logs (canonical route)",
)
async def list_audit_logs(
    request: Request,
    auth: Annotated[UserContext, Depends(get_current_user)],
    repo: Annotated[IAuditLogRepository, Depends(get_audit_log_repository)],
    session: Annotated[AsyncSession, Depends(get_db)],
    workspace_id: UUID | None = Query(None, description="Target workspace ID for diagnostic audit inspection"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    query: str | None = Query(None, description="Search term across action, resource, or user"),
    action: str | None = Query(None, description="Filter by action name"),
    start_date: datetime | None = Query(None, description="Filter logs on or after timestamp"),
    end_date: datetime | None = Query(None, description="Filter logs on or before timestamp"),
) -> PaginatedResponse[AuditLogDTO]:
    """Retrieve audit logs for the authenticated user's workspace with true pagination and search.

    DEC-11 / D-21 Option 2:
    - Customer workspace OWNER and ADMIN access their own workspace audit logs.
    - Platform roles are strictly prohibited from ordinary workspace audit logs and must
      use the dedicated platform diagnostic endpoint `/platform/audit-logs/inspect`.
    - Direct calls with diagnostic ticket justification are supported for backward compatibility.
    """
    user_role = Role.from_str(str(auth.role))

    # 1. Deny Platform Support explicitly (DEC-11 policy boundary)
    if user_role == Role.PLATFORM_SUPPORT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform support role is prohibited from accessing audit logs.",
        )

    # 2. Check if request is hitting customer audit route with platform role
    req_path = getattr(getattr(request, "url", None), "path", "")
    if req_path in CUSTOMER_AUDIT_PATHS and user_role in (Role.PLATFORM_ADMIN, Role.PLATFORM_AUDITOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform roles are prohibited from ordinary workspace audit logs. Use the dedicated platform diagnostic endpoint.",
        )

    # 3. Platform Diagnostic Access (Auditor or Platform Admin with ticket)
    if user_role in (Role.PLATFORM_AUDITOR, Role.PLATFORM_ADMIN):
        raw_ticket = request.headers.get("X-Justification-Ticket-ID")
        ticket_id = validate_diagnostic_ticket(raw_ticket)

        target_ws_id = workspace_id or (UUID(auth.tenant_id) if auth.tenant_id else None)
        if not target_ws_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant or workspace ID is required for diagnostic audit log inspection.",
            )

        await record_diagnostic_access(
            session=session,
            user_id=auth.id,
            user_role=user_role.value,
            action="DIAGNOSTIC_AUDIT_LOG_READ",
            resource_type="audit_logs",
            resource_id=str(target_ws_id),
            ticket_id=ticket_id,
            tenant_id=target_ws_id,
        )
        tenant_id = target_ws_id

    # 4. Standard customer workspace administrative roles (OWNER, ADMIN)
    elif user_role in (Role.ADMIN, Role.OWNER):
        if not auth.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant ID is required in the user context to fetch audit logs.",
            )
        tenant_id = UUID(auth.tenant_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access audit logs.",
        )

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
    req_id = getattr(getattr(request, "state", None), "correlation_id", str(uuid.uuid4()))

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


@router.get(
    "/platform/audit-logs/inspect",
    response_model=PaginatedResponse[AuditLogDTO],
    status_code=status.HTTP_200_OK,
    summary="Platform diagnostic inspection of workspace audit logs (D-21 Option 2)",
)
@router.get(
    "/platform/audit-logs",
    response_model=PaginatedResponse[AuditLogDTO],
    status_code=status.HTTP_200_OK,
    summary="Platform diagnostic inspection of workspace audit logs alias (D-21 Option 2)",
)
async def inspect_platform_audit_logs(
    request: Request,
    auth: Annotated[UserContext, Depends(get_current_user)],
    repo: Annotated[IAuditLogRepository, Depends(get_audit_log_repository)],
    session: Annotated[AsyncSession, Depends(get_db)],
    workspace_id: UUID = Query(..., description="Target workspace ID for diagnostic audit inspection"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    query: str | None = Query(None, description="Search term across action, resource, or user"),
    action: str | None = Query(None, description="Filter by action name"),
    start_date: datetime | None = Query(None, description="Filter logs on or after timestamp"),
    end_date: datetime | None = Query(None, description="Filter logs on or before timestamp"),
) -> PaginatedResponse[AuditLogDTO]:
    """Dedicated Platform Diagnostic Audit Inspection Endpoint (D-21 Option 2).

    Requires:
    - Platform diagnostic role (PLATFORM_ADMIN or PLATFORM_AUDITOR).
    - Mandatory X-Justification-Ticket-ID header.
    - Target workspace ID.
    - Transactional, immutable audit trail generation.
    """
    user_role = Role.from_str(str(auth.role))

    if user_role == Role.PLATFORM_SUPPORT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform support role is prohibited from accessing audit logs.",
        )

    if user_role not in (Role.PLATFORM_ADMIN, Role.PLATFORM_AUDITOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform diagnostic roles can access this endpoint.",
        )

    raw_ticket = request.headers.get("X-Justification-Ticket-ID")
    ticket_id = validate_diagnostic_ticket(raw_ticket)

    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target workspace ID is required for platform audit inspection.",
        )

    await record_diagnostic_access(
        session=session,
        user_id=auth.id,
        user_role=user_role.value,
        action="DIAGNOSTIC_AUDIT_LOG_READ",
        resource_type="audit_logs",
        resource_id=str(workspace_id),
        ticket_id=ticket_id,
        tenant_id=workspace_id,
    )

    skip = (page - 1) * page_size

    logs, total_count = await repo.search_logs(
        tenant_id=workspace_id,
        query=query,
        action=action,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=page_size,
    )

    items = [AuditLogDTO.model_validate(log) for log in logs]
    total_pages = max(1, math.ceil(total_count / page_size)) if total_count > 0 else 1
    req_id = getattr(getattr(request, "state", None), "correlation_id", str(uuid.uuid4()))

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
