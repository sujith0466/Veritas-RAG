"""Celery Vector Storage Task (`sync_vectors_to_qdrant_task`).

Runs asynchronous batch point upsert and payload indexing on the `ingestion` queue (`ADR-M3-001`).
Enforces jittered exponential backoff retry policies (`ADR-M3-002`) for transient
Qdrant connection (`VEC_003`) and indexing timeout (`VEC_005`) errors while failing fast
on fatal schema or dimension errors (`VEC_001`, `VEC_002`, `VEC_004`).
"""

import asyncio
from typing import Any
import uuid

import structlog

from backend.database.engine import get_session_factory
from backend.modules.vector.schemas.errors import ErrorSeverity, VectorDomainException
from backend.modules.vector.services.vector_service import VectorStorageService
from backend.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, queue="ingestion", max_retries=5, acks_late=True)
def sync_vectors_to_qdrant_task(
    self: Any,
    document_id: str,
    document_version_id: str,
    tenant_id: str,
    collection_name: str | None = None,
) -> dict[str, Any]:
    """Background Celery task for synchronizing staged document vectors into Qdrant (`ADR-M3-001`).

    Args:
        document_id: Document UUID string.
        document_version_id: Document version UUID string.
        tenant_id: Tenant namespace identifier.
        collection_name: Optional target collection name override.

    Returns:
        Dictionary summary containing upserted point count and completion status.
    """
    try:
        return asyncio.run(
            _async_sync_vectors_task(
                self,
                document_id,
                document_version_id,
                tenant_id,
                collection_name,
            )
        )
    except VectorDomainException as exc:
        if exc.severity == ErrorSeverity.RECOVERABLE and self.request.retries < self.max_retries:
            countdown = int(2**self.request.retries * 5)
            logger.warning(
                "Recoverable Qdrant error; scheduling exponential backoff retry",
                error_code=exc.code,
                attempt=self.request.retries + 1,
                countdown_s=countdown,
            )
            raise self.retry(exc=exc, countdown=countdown) from exc
        logger.error("Fatal vector synchronization error or retries exhausted", error_code=exc.code, error=str(exc))
        raise
    except Exception as exc:
        if self.request.retries < self.max_retries:
            countdown = int(2**self.request.retries * 5)
            logger.warning("Unhandled sync error; scheduling retry", attempt=self.request.retries + 1, error=str(exc))
            raise self.retry(exc=exc, countdown=countdown) from exc
        raise


async def _async_sync_vectors_task(
    task_instance: Any,
    document_id: str,
    document_version_id: str,
    tenant_id: str,
    collection_name: str | None,
) -> dict[str, Any]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        service = VectorStorageService(session=session)
        upserted = await service.sync_document_vectors(
            document_id=document_id,
            document_version_id=document_version_id,
            tenant_id=tenant_id,
            collection_name=collection_name,
        )
        return {
            "tenant_id": tenant_id,
            "document_id": document_id,
            "document_version_id": document_version_id,
            "upserted_points": upserted,
            "status": "COMPLETED",
        }
