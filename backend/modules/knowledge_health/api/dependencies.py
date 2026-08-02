"""API Dependencies for Knowledge Health & Lifecycle (`ADR-005`)."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies.auth import require_role
from backend.core.dependencies.database import get_db as get_db_session
from backend.core.permissions.rbac import Role
from backend.modules.knowledge_health.services.health_service import KnowledgeHealthOrchestrator

AdminAuth = Annotated[dict, Depends(require_role(Role.ADMIN))]


async def get_health_orchestrator(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> KnowledgeHealthOrchestrator:
    """Dependency yielding a configured `KnowledgeHealthOrchestrator` domain service."""
    return KnowledgeHealthOrchestrator(session)
