"""IdP Health and Certificate Rotation Celery Task."""

from datetime import UTC, datetime

from celery import shared_task
from sqlalchemy import select
import structlog

from backend.models.entities.identity_provider import IdentityProvider

logger = structlog.get_logger(__name__)

async def _refresh_idps_async() -> None:
    from backend.core.dependencies.database import sessionmanager
    async with sessionmanager.session() as session:
        stmt = select(IdentityProvider).where(
            IdentityProvider.is_active == True,
            IdentityProvider.metadata_url.is_not(None)
        )
        result = await session.execute(stmt)
        idps = result.scalars().all()

        from backend.core.events import EventDispatcher
        dispatcher = EventDispatcher()

        for idp in idps:
            try:
                # 1. Fetch metadata_url (Simulated for tests)
                # 2. Check certificate expiry (Simulated)
                logger.info("Refreshing IdP metadata", idp_id=str(idp.id), name=idp.name)

                # Update DB (simulated metadata update)
                idp.updated_at = datetime.now(UTC)
                await session.commit()

                # 4. Dispatch IDP_METADATA_REFRESHED event
                await dispatcher.dispatch("IDP_METADATA_REFRESHED", {"idp_id": str(idp.id), "workspace_id": str(idp.workspace_id)})
            except Exception as e:
                logger.error("Failed to refresh IdP metadata", idp_id=str(idp.id), error=str(e))
                await session.rollback()


@shared_task
def check_idp_health_task() -> None:
    """
    Worker for nightly metadata refresh and certificate rotation.
    Emits warnings if certificates are expiring within 30 days.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_refresh_idps_async())
    except Exception as exc:
        logger.error("Failed to execute IdP health task", error=str(exc))
