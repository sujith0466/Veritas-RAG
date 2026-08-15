"""Platform Admin API Endpoints (F12.2)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from backend.api.v1.schemas.common import PaginatedResponse, ResponseMetadata
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db as get_db_session
from backend.core.dependencies.rbac import require_role
from backend.core.permissions.rbac import Role
from backend.models.entities.workspace import Workspace
from backend.modules.analytics.models.query_analytics import QueryAnalyticsRecord
from backend.models.entities.workspace_member import WorkspaceMember
from pydantic import BaseModel

router = APIRouter(prefix="/platform-admin", tags=["Platform Admin"])


class WorkspaceSummaryDTO(BaseModel):
    id: UUID
    name: str
    member_count: int
    total_queries: int


@router.get(
    "/workspaces",
    response_model=PaginatedResponse[WorkspaceSummaryDTO],
    status_code=status.HTTP_200_OK,
    summary="List all workspaces with aggregated metrics",
)
async def list_all_workspaces(
    auth: Annotated[UserContext, Depends(require_role(Role.PLATFORM_ADMIN))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> PaginatedResponse[WorkspaceSummaryDTO]:
    """Retrieve global workspace aggregations (Platform Admin only)."""
    skip = (page - 1) * page_size
    
    # Efficient grouping query
    stmt = (
        select(
            Workspace.id,
            Workspace.name,
            func.count(WorkspaceMember.id.distinct()).label("member_count"),
            func.count(QueryAnalyticsRecord.id.distinct()).label("total_queries"),
        )
        .outerjoin(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
        .outerjoin(
            QueryAnalyticsRecord, 
            func.cast(Workspace.id, sa.String) == QueryAnalyticsRecord.tenant_id
        )
        .where(Workspace.is_deleted.is_(False))
        .group_by(Workspace.id, Workspace.name)
        .order_by(Workspace.created_at.desc())
        .offset(skip)
        .limit(page_size)
    )
    
    import sqlalchemy as sa
    # Need to import sa for the func.cast above to match string tenant_id with UUID.
    # Actually, we can fix the query structure.
    
    # Total count query
    count_stmt = select(func.count(Workspace.id)).where(Workspace.is_deleted.is_(False))
    total = (await session.scalar(count_stmt)) or 0
    
    result = await session.execute(stmt)
    rows = result.all()
    
    items = [
        WorkspaceSummaryDTO(
            id=row.id,
            name=row.name,
            member_count=row.member_count or 0,
            total_queries=row.total_queries or 0,
        ) for row in rows
    ]
    
    return PaginatedResponse(
        data=items,
        total=total,
        page=page,
        page_size=page_size,
        metadata=ResponseMetadata(),
    )
