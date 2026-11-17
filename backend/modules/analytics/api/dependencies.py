"""API Dependencies for Query Analytics (`Phase 4 Milestone 1`)."""

from typing import Annotated
import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db as get_db_session
from backend.models.entities.workspace_member import MemberStatus
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.modules.analytics.repositories.analytics_repository import AnalyticsRepository
from backend.modules.analytics.services.analytics_service import QueryAnalyticsService
from backend.modules.analytics.services.reporting_service import ReportingService


async def require_workspace_analytics_admin_or_owner(
    current_user: Annotated[UserContext, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserContext:
    """Authoritatively enforce active OWNER or ADMIN workspace membership for query analytics.

    Enforces DEC-07:
    1. Fails closed on missing or malformed workspace context (HTTP 400).
    2. Prohibits generic PLATFORM_ADMIN/SUPPORT/AUDITOR bypass of customer query data (HTTP 403).
    3. Authoritatively queries PostgreSQL workspace_members to defeat stale/spoofed JWT claims (HTTP 403).
    """
    ws_raw = current_user.workspace_id or current_user.tenant_id
    if not ws_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing workspace context: tenant_id or workspace_id is required.",
        )

    try:
        ws_uuid = uuid.UUID(str(ws_raw))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace identifier format: must be a valid UUID.",
        )

    repo = WorkspaceMemberRepository(session)
    member = await repo.get_membership(
        workspace_id=ws_uuid,
        user_id=current_user.id,
        include_suspended=False,
    )
    if not member or member.status != MemberStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You are not an active member of this workspace.",
        )

    role_str = (member.role or "").strip().upper()
    if role_str not in ("OWNER", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Requires workspace Admin or Owner role.",
        )

    return current_user


AnalyticsAuth = Annotated[UserContext, Depends(require_workspace_analytics_admin_or_owner)]
AdminAuth = Annotated[UserContext, Depends(require_workspace_analytics_admin_or_owner)]


async def get_analytics_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QueryAnalyticsService:
    """Dependency yielding a configured `QueryAnalyticsService` instance."""
    repository = AnalyticsRepository(session)
    return QueryAnalyticsService(repository)


async def get_reporting_service(
    analytics_service: Annotated[QueryAnalyticsService, Depends(get_analytics_service)],
) -> ReportingService:
    """Dependency yielding a configured `ReportingService` instance."""
    return ReportingService(analytics_service)
