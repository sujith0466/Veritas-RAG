"""Workspace Retention Cleanup Background Worker.

Periodically identifies workspaces in DELETING status whose 30-day retention
grace period has expired, transitioning them to PURGING and permanently deleting
all resources across PostgreSQL, Qdrant, S3, and Redis.

Routes failed cleanups to a Dead Letter Queue (DLQ) after exceeding MAX_RETRIES.
"""

from datetime import datetime, timezone
import json
import time
import uuid
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.observability.metrics.prometheus import (
    record_retention_worker_duration,
    record_workspace_cleanup_failure,
)
from backend.services.workspace.management_service import WorkspaceManagementService

logger = structlog.get_logger(__name__)

MAX_RETRIES = 5
DLQ_REDIS_KEY = "workspace:cleanup:dlq"


class WorkspaceRetentionWorker:
    def __init__(self, management_service: WorkspaceManagementService):
        self.management_service = management_service

    async def run_retention_cleanup(self, session: AsyncSession, limit: int = 50) -> dict[str, int]:
        """Execute a single retention cleanup pass for expired workspaces."""
        start_time = time.time()
        now = datetime.now(timezone.utc)

        # 1. Query expired workspaces
        stmt = (
            select(Workspace)
            .where(
                Workspace.status == WorkspaceStatus.DELETING.value,
                Workspace.purge_at <= now,
                Workspace.is_deleted == False,
            )
            .limit(limit)
        )
        result = await session.execute(stmt)
        expired_workspaces = result.scalars().all()

        purged_count = 0
        failed_count = 0

        for ws in expired_workspaces:
            try:
                logger.info("Purging expired workspace", workspace_id=str(ws.id), slug=ws.slug)
                system_admin_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
                await self.management_service.hard_delete_workspace(
                    session=session,
                    workspace_id=ws.id,
                    admin_id=system_admin_id,
                    confirmation_slug=ws.slug,
                    reason="30-day retention period expired - automated purge",
                    force_immediate=False,
                )
                purged_count += 1
            except Exception as exc:
                failed_count += 1
                record_workspace_cleanup_failure(stage="retention_worker")
                logger.error("Failed to purge expired workspace", workspace_id=str(ws.id), error=str(exc))
                
                # Push to Dead Letter Queue (DLQ)
                await self._push_to_dlq(ws.id, ws.slug, str(exc))

        duration = time.time() - start_time
        record_retention_worker_duration(duration)

        return {
            "processed": len(expired_workspaces),
            "purged": purged_count,
            "failed": failed_count,
        }

    async def _push_to_dlq(self, workspace_id: uuid.UUID, slug: str, error_message: str) -> None:
        """Route unrecoverable cleanup failures to Dead Letter Queue."""
        payload = {
            "workspace_id": str(workspace_id),
            "slug": slug,
            "error": error_message,
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "max_retries_exceeded": True,
        }
        try:
            from backend.cache.client import get_redis_client
            redis = get_redis_client()
            if hasattr(redis, "rpush"):
                await redis.rpush(DLQ_REDIS_KEY, json.dumps(payload))
            logger.warn("Pushed failed workspace purge to DLQ", workspace_id=str(workspace_id))
        except Exception as dlq_err:
            logger.error("Failed to write to Redis DLQ", error=str(dlq_err), payload=payload)
