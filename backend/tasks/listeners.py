"""Event listeners for robust RAG pipeline orchestration."""

import uuid

import structlog

from backend.core.events.dispatcher import get_dispatcher
from backend.core.events.types import EventType
from backend.document.events import EVENT_DOCUMENT_PROCESSED
from backend.document.models.status import DocumentStatus

logger = structlog.get_logger(__name__)

async def handle_document_processed(event) -> None:
    """Trigger chunking when ingestion is complete."""
    logger.info("Pipeline Orchestrator: Received DocumentProcessed event, triggering chunking", event_id=event.event_id)
    try:
        from backend.database.engine import get_session_factory
        from backend.modules.chunking.workers.tasks import process_document_chunking_task
        session_factory = get_session_factory()

        async with session_factory() as session:
            from backend.document.models.document import Document
            doc_id = event.data.get("document_id") or getattr(event, "document_id", None)
            if not doc_id:
                logger.error("Document not found in event", event_data=event.data)
                return
            doc = await session.get(Document, uuid.UUID(str(doc_id)))
            if not doc:
                logger.error("Document not found in db", doc_id=doc_id)
                return

            tenant_id = doc.tenant_id
            document_id = str(doc.id)
            version_id = str(doc.latest_version_id)

            # Update state to CHUNKING
            doc.status = DocumentStatus.CHUNKING
            await session.commit()

            logger.info("Dispatching chunking task", document_id=document_id)
            process_document_chunking_task.apply_async(
                args=[tenant_id, document_id, version_id],
                queue="ingestion"
            )
    except Exception as e:
        logger.error("Pipeline Orchestrator: Failed to handle document processed", error=str(e))


async def handle_chunking_completed(event) -> None:
    """Trigger embedding when chunking is complete."""
    logger.info("Pipeline Orchestrator: Received ChunkingCompleted event, triggering embeddings", event_id=event.event_id)
    try:
        from backend.database.engine import get_session_factory
        from backend.modules.embedding.services.embedding_service import EmbeddingService
        from backend.modules.embedding.workers.tasks import process_embedding_batch_task
        session_factory = get_session_factory()

        async with session_factory() as session:
            from backend.document.models.document import Document
            doc_id = event.data.get("document_id") or getattr(event, "document_id", None)
            if not doc_id:
                return
            doc = await session.get(Document, uuid.UUID(str(doc_id)))
            if not doc:
                return

            doc.status = DocumentStatus.EMBEDDING
            await session.commit()

            from backend.core.config import get_settings
            from backend.modules.embedding.repositories.embedding_repository import (
                EmbeddingRepository,
            )
            settings = get_settings()

            provider = settings.embeddings.default_provider
            if provider == "openai":
                model_name = settings.embeddings.openai_model
            elif provider == "cohere":
                model_name = settings.embeddings.cohere_model
            else:
                model_name = settings.embeddings.local_model

            repo = EmbeddingRepository(session)
            emb_service = EmbeddingService(repository=repo)
            job = await emb_service.initiate_embedding_job(
                tenant_id=doc.tenant_id,
                document_id=doc.id,
                document_version_id=doc.latest_version_id,
                provider=provider,
                model_name=model_name,
                force_reembed=False
            )
            await session.commit()

            process_embedding_batch_task.apply_async(
                args=[str(job.id), doc.tenant_id, 100, False],
                queue="embeddings"
            )
    except Exception as e:
        logger.error("Pipeline Orchestrator: Failed to handle chunking completed", error=str(e))


async def handle_embedding_completed(event) -> None:
    """Trigger vector sync when embeddings are complete."""
    logger.info("Pipeline Orchestrator: Received EmbeddingCompleted event, triggering vector sync", event_id=event.event_id)
    try:
        from backend.database.engine import get_session_factory
        from backend.modules.vector.workers.tasks import sync_vectors_to_qdrant_task
        session_factory = get_session_factory()

        async with session_factory() as session:
            from backend.document.models.document import Document
            if hasattr(event, "payload") and event.payload:
                doc_id = event.payload.document_id
            else:
                doc_id = event.data.get("document_id") or getattr(event, "document_id", None)
            if not doc_id:
                return
            doc = await session.get(Document, uuid.UUID(str(doc_id)))
            if not doc:
                return

            doc.status = DocumentStatus.VECTOR_SYNC
            await session.commit()

            sync_vectors_to_qdrant_task.apply_async(
                args=[str(doc.id), str(doc.latest_version_id), doc.tenant_id],
                queue="indexing"
            )
    except Exception as e:
        logger.error("Pipeline Orchestrator: Failed to handle embedding completed", error=str(e))

async def handle_vector_sync_completed(event) -> None:
    """Mark document as READY."""
    logger.info("Pipeline Orchestrator: Received VectorSyncCompleted event, marking READY", event_id=event.event_id)
    try:
        from backend.database.engine import get_session_factory
        session_factory = get_session_factory()

        async with session_factory() as session:
            from backend.document.models.document import Document
            if hasattr(event, "payload") and event.payload:
                doc_id = event.payload.document_id
            else:
                doc_id = event.data.get("document_id") or getattr(event, "document_id", None)
            if not doc_id:
                return
            doc = await session.get(Document, uuid.UUID(str(doc_id)))
            if not doc:
                return

            doc.status = DocumentStatus.READY
            await session.commit()
            logger.info("Document is now READY for RAG", document_id=str(doc.id))
    except Exception as e:
        logger.error("Pipeline Orchestrator: Failed to handle vector sync completed", error=str(e))


def register_pipeline_listeners() -> None:
    """Register all listeners to the EventDispatcher."""
    dispatcher = get_dispatcher()
    dispatcher.subscribe(EVENT_DOCUMENT_PROCESSED, handle_document_processed)
    dispatcher.subscribe(EventType.CHUNKING_COMPLETED, handle_chunking_completed)
    dispatcher.subscribe(EventType.EMBEDDING_COMPLETED, handle_embedding_completed)
    dispatcher.subscribe(EventType.VECTORS_INDEXED, handle_vector_sync_completed)
    logger.info("RAG Pipeline Orchestrator event listeners registered.")
