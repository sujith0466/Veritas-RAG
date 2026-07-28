"""API Dependencies for Query Analytics (`Phase 4 Milestone 1`)."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies.auth import require_role
from backend.core.dependencies.database import get_db as get_db_session
from backend.core.permissions.rbac import Role
from backend.modules.analytics.repositories.analytics_repository import \
    AnalyticsRepository
from backend.modules.analytics.services.analytics_service import \
    QueryAnalyticsService
from backend.modules.analytics.services.reporting_service import \
    ReportingService

from backend.core.auth.context import UserContext

AnalyticsAuth = Annotated[UserContext, Depends(require_role(Role.VIEWER))]
AdminAuth = Annotated[UserContext, Depends(require_role(Role.ADMIN))]


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
