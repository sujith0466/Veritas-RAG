import asyncio
from uuid import UUID

from celery import shared_task

from backend.core.database import get_db_session
from backend.core.events.dispatcher import EventDispatcher
from backend.modules.knowledge_base.schemas.staleness_dto import StalenessPolicyDTO
from backend.modules.knowledge_base.services.staleness_service import StalenessService


async def _evaluate_staleness_async(workspace_id: UUID) -> None:
    async with get_db_session() as session:
        event_dispatcher = EventDispatcher(session)
        service = StalenessService(session, event_dispatcher)

        # We would typically load the workspace's specific staleness policy from settings
        # For simplicity, we use the default policy here
        policy = StalenessPolicyDTO()

        await service.evaluate_workspace_staleness(workspace_id, policy)


@shared_task(name="evaluate_workspace_staleness_task")
def evaluate_workspace_staleness_task(workspace_id: str) -> None:
    """Celery background task to evaluate workspace staleness and tag documents."""
    asyncio.run(_evaluate_staleness_async(UUID(workspace_id)))
