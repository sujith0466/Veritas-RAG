"""Folder Retention Cleanup Background Worker.

Periodically identifies folders in soft-deleted status whose 30-day retention
grace period has expired, transitioning them to PURGING and permanently deleting
all resources.
"""

import time

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.services.folder_service import FolderService
from backend.tasks.folders import hard_delete_folder_subtree

logger = structlog.get_logger(__name__)

class FolderRetentionWorker:
    def __init__(self, folder_service: FolderService):
        self.folder_service = folder_service

    async def run_retention_cleanup(self, session: AsyncSession, limit: int = 50) -> dict[str, int]:
        """Execute a single retention cleanup pass for expired folders."""
        start_time = time.time()

        # 1. Query eligible folders using repository
        expired_folders = await self.folder_service.repository.get_eligible_for_purge(limit=limit)

        purged_count = 0
        failed_count = 0

        for folder in expired_folders:
            try:
                logger.info("Scheduling expired folder for purge", folder_id=str(folder.id), workspace_id=str(folder.workspace_id))

                # Dispatch the celery task
                hard_delete_folder_subtree.apply_async(
                    args=[str(folder.id), str(folder.workspace_id)]
                )

                purged_count += 1
            except Exception as exc:
                failed_count += 1
                logger.error("Failed to schedule folder for purge", folder_id=str(folder.id), error=str(exc))

        duration = time.time() - start_time
        logger.info("Folder retention cleanup complete", duration_seconds=duration, purged_count=purged_count, failed_count=failed_count)

        return {"scheduled_for_purge": purged_count, "failed": failed_count}
