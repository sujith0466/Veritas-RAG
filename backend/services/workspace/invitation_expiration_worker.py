"""Workspace Invitation Expiration Background Worker.

Periodically queries expired PENDING invitations, batch-transitions them to EXPIRED,
emits domain events, and writes structured audit logs.
"""

import time

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.services.workspace.invitation_service import WorkspaceInvitationService

logger = structlog.get_logger(__name__)


class WorkspaceInvitationExpirationWorker:
    """Hourly background worker for invitation expiration cleanup."""

    def __init__(self, invitation_service: WorkspaceInvitationService):
        self.invitation_service = invitation_service

    async def run_expiration_pass(self, session: AsyncSession) -> dict[str, int | float]:
        """Execute a single pass to expire stale pending invitations."""
        start_time = time.time()
        logger.info("Starting workspace invitation expiration worker pass")

        expired_count = await self.invitation_service.run_expiration_cleanup(session)
        duration = time.time() - start_time

        logger.info(
            "Completed workspace invitation expiration worker pass",
            expired_count=expired_count,
            duration_seconds=duration,
        )

        return {
            "expired_count": expired_count,
            "duration_seconds": duration,
        }
