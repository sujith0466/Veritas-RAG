"""Celery background worker for syncing document metadata to Qdrant."""

import uuid

from backend.core.logger import get_logger
from backend.database.session import get_session_factory
from backend.document.repositories.document_repository import DocumentRepository
from backend.document.services.vector_service import VectorStorageService
from backend.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="document.sync_document_metadata_to_vectors_job",
    queue="vector_ops",
    max_retries=3,
    acks_late=True,
)
def sync_document_metadata_to_vectors_job(
    self, document_id: str, tenant_id: str
) -> None:
    """Synchronize updated document metadata to Qdrant vectors."""
    logger.info(f"Starting metadata sync for document {document_id}")
    import asyncio
    asyncio.run(_async_sync_metadata(uuid.UUID(document_id), tenant_id))


async def _async_sync_metadata(document_id: uuid.UUID, tenant_id: str) -> None:
    """Async execution for syncing metadata."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        doc_repo = DocumentRepository()
        doc = await doc_repo.get_by_id_with_versions(document_id, tenant_id, session)
        if not doc:
            logger.warning(f"Document {document_id} not found during sync.")
            return

        vector_service = VectorStorageService()
        await vector_service.sync_metadata(doc)
        logger.info(f"Successfully synced metadata for document {document_id}")
