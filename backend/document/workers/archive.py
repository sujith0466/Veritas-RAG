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
                from backend.document.models.document import Document
                from backend.document.models.status import DocumentStatus
                doc = await session.get(Document, uuid.UUID(document_id))
                if doc and doc.status != DocumentStatus.READY.value:
                    doc.status = DocumentStatus.READY.value
                    await session.commit()

                log.info("Finished restore vector sync job and transitioned document to READY", synced_count=synced_count)
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
        if hasattr(self, "request") and self.request.retries >= self.max_retries:
            # Mark document as FAILED so failure is observable
            async def _mark_failed():
                async with get_session_factory()() as session:
                    from backend.document.models.document import Document
                    from backend.document.models.status import DocumentStatus
                    doc = await session.get(Document, uuid.UUID(document_id))
                    if doc:
                        doc.status = DocumentStatus.FAILED.value
                        await session.commit()
            try:
                asyncio.run(_mark_failed())
            except Exception as mark_err:
                logger.warning("Failed to mark document as FAILED after retries exhausted", error=str(mark_err))
            raise exc
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 5)
