"""Celery workers for document archiving and vector cleanup.

Handles asynchronous removal of vectors from Qdrant upon archive and
re-syncing vectors upon restore (`ADR-005`, `F5.5`).
"""

import asyncio
import uuid

import structlog

from backend.database.session import get_session_factory
from backend.modules.vector.services.vector_service import VectorStorageService
from backend.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

@celery_app.task(
    name="remove_archived_document_vectors_job",
    bind=True,
    max_retries=3,
    acks_late=True,
)
def remove_archived_document_vectors_job(self, document_id: str, tenant_id: str) -> dict:
    """Removes all Qdrant vectors for an archived document."""
    async def _run() -> dict:
        log = logger.bind(document_id=document_id, tenant_id=tenant_id)
        log.info("Starting archive vector cleanup job")

        async with get_session_factory()() as session:
            vector_service = VectorStorageService(session=session)

            try:
                deleted_count = await vector_service.remove_archived_document_vectors(
                    document_id=document_id,
                    tenant_id=tenant_id
                )
                log.info("Finished archive vector cleanup job", deleted_count=deleted_count)
                return {"status": "success", "deleted_ops": deleted_count}
            except Exception as e:
                log.error("Archive vector cleanup failed", error=str(e))
                raise e

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error(
            "Archive vector cleanup worker failed",
            error=str(exc),
            document_id=document_id,
        )
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 5)


@celery_app.task(
    name="restore_archived_document_vectors_job",
    bind=True,
    max_retries=3,
    acks_late=True,
)
def restore_archived_document_vectors_job(self, document_id: str, version_id: str, tenant_id: str) -> dict:
    """Restores an archived document's vectors by re-syncing its latest version."""
    async def _run() -> dict:
        log = logger.bind(document_id=document_id, version_id=version_id, tenant_id=tenant_id)
        log.info("Starting restore vector sync job")

        async with get_session_factory()() as session:
            vector_service = VectorStorageService(session=session)

            try:
                synced_count = await vector_service.sync_document_vectors(
                    document_id=uuid.UUID(document_id),
                    document_version_id=uuid.UUID(version_id),
                    tenant_id=tenant_id
                )
                log.info("Finished restore vector sync job", synced_count=synced_count)
                return {"status": "success", "synced_ops": synced_count}
            except Exception as e:
                log.error("Restore vector sync failed", error=str(e))
                raise e

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error(
            "Restore vector sync worker failed",
            error=str(exc),
            document_id=document_id,
        )
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 5)
