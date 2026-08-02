"""Dependencies for dashboard API endpoints."""

from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.modules.dashboard.services.dashboard_service import DashboardService

DashboardAuth = Annotated[Any, Depends(get_current_user)]


async def get_dashboard_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DashboardService:
    """Dependency injector for DashboardService."""
    return DashboardService(session)
