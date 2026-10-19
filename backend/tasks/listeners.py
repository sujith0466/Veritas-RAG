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
        from backend.document.services.failure_service import PipelineFailureSynchronizer
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

            event_data = getattr(event, "data", {}) if isinstance(getattr(event, "data", None), dict) else {}
            payload_obj = getattr(event, "payload", None)

            target_ver_id = (
                event_data.get("document_version_id")
                or event_data.get("version_id")
                or (getattr(payload_obj, "document_version_id", None) if payload_obj else None)
                or (getattr(payload_obj, "version_id", None) if payload_obj else None)
                or doc.latest_version_id
            )
            version_id = str(target_ver_id)

            logger.info("Dispatching chunking task", document_id=document_id, version_id=version_id)
            try:
                process_document_chunking_task.apply_async(
                    args=[tenant_id, document_id, version_id],
                    queue="ingestion"
                )
                # Update state to CHUNKING strictly AFTER successful dispatch
                if doc.status != DocumentStatus.READY:
                    doc.status = DocumentStatus.CHUNKING
                    await session.commit()
            except Exception as dispatch_exc:
                logger.error("Failed to dispatch chunking task to broker", document_id=document_id, error=str(dispatch_exc))
                await PipelineFailureSynchronizer.record_pipeline_failure(
                    session=session,
                    document_id=doc.id,
                    failing_stage="chunking_dispatch",
                    error_code="BROKER_DISPATCH_FAILED",
                    error_message=f"Broker dispatch failed: {dispatch_exc!s}",
                    exception=dispatch_exc,
                    tenant_id=tenant_id,
                    version_id=uuid.UUID(version_id) if version_id else None,
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
        from backend.document.services.failure_service import PipelineFailureSynchronizer
        session_factory = get_session_factory()

        async with session_factory() as session:
            from backend.document.models.document import Document
            event_data = getattr(event, "data", {}) if isinstance(getattr(event, "data", None), dict) else {}
            payload_obj = getattr(event, "payload", None)

            doc_id = (
                event_data.get("document_id")
                or (getattr(payload_obj, "document_id", None) if payload_obj else None)
                or getattr(event, "document_id", None)
            )
            if not doc_id:
                return
            doc = await session.get(Document, uuid.UUID(str(doc_id)))
            if not doc:
                return

            target_ver_id = (
                getattr(event, "document_version_id", None)
                or getattr(event, "version_id", None)
                or event_data.get("document_version_id")
                or event_data.get("version_id")
                or (getattr(payload_obj, "document_version_id", None) if payload_obj else None)
                or (getattr(payload_obj, "version_id", None) if payload_obj else None)
                or doc.latest_version_id
            )
            target_ver_uuid = uuid.UUID(str(target_ver_id)) if target_ver_id else doc.latest_version_id

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
                document_version_id=target_ver_uuid,
                provider=provider,
                model_name=model_name,
                force_reembed=False
            )
            await session.commit()

            try:
                process_embedding_batch_task.apply_async(
                    args=[str(job.id), doc.tenant_id, 100, False],
                    queue="embeddings"
                )
                # Preserve READY status for online serving during re-indexing; only set EMBEDDING after dispatch
                if doc.status != DocumentStatus.READY:
                    doc.status = DocumentStatus.EMBEDDING
                    await session.commit()
            except Exception as dispatch_exc:
                logger.error("Failed to dispatch embedding task to broker", document_id=str(doc.id), error=str(dispatch_exc))
                await PipelineFailureSynchronizer.record_pipeline_failure(
                    session=session,
                    document_id=doc.id,
                    failing_stage="embedding_dispatch",
                    error_code="BROKER_DISPATCH_FAILED",
                    error_message=f"Broker dispatch failed: {dispatch_exc!s}",
                    exception=dispatch_exc,
                    tenant_id=doc.tenant_id,
                    version_id=target_ver_uuid,
                    embedding_job_id=job.id,
                )
    except Exception as e:
        logger.error("Pipeline Orchestrator: Failed to handle chunking completed", error=str(e))


async def handle_embedding_completed(event) -> None:
    """Trigger vector sync when embeddings are complete."""
    logger.info("Pipeline Orchestrator: Received EmbeddingCompleted event, triggering vector sync", event_id=event.event_id)
    try:
        from backend.database.engine import get_session_factory
        from backend.modules.vector.workers.tasks import sync_vectors_to_qdrant_task
        from backend.document.services.failure_service import PipelineFailureSynchronizer
        session_factory = get_session_factory()

        async with session_factory() as session:
            from backend.document.models.document import Document
            payload_obj = getattr(event, "payload", None)
            event_data = getattr(event, "data", {}) if isinstance(getattr(event, "data", None), dict) else {}

            doc_id = (
                (getattr(payload_obj, "document_id", None) if payload_obj else None)
                or event_data.get("document_id")
                or getattr(event, "document_id", None)
            )
            if not doc_id:
                return
            doc = await session.get(Document, uuid.UUID(str(doc_id)))
            if not doc:
                return

            target_ver_id = (
                (getattr(payload_obj, "document_version_id", None) if payload_obj else None)
                or (getattr(payload_obj, "version_id", None) if payload_obj else None)
                or getattr(event, "document_version_id", None)
                or getattr(event, "version_id", None)
                or event_data.get("document_version_id")
                or event_data.get("version_id")
                or doc.latest_version_id
            )
            target_ver_uuid = uuid.UUID(str(target_ver_id)) if target_ver_id else doc.latest_version_id

            # Skip duplicate task dispatch if already in VECTOR_SYNC
            if doc.status == DocumentStatus.VECTOR_SYNC:
                logger.info(
                    "Pipeline Orchestrator: Document already in VECTOR_SYNC state; skipping duplicate dispatch",
                    document_id=str(doc.id),
                )
                return

            try:
                sync_vectors_to_qdrant_task.apply_async(
                    args=[str(doc.id), str(target_ver_id), doc.tenant_id],
                    queue="indexing"
                )
                # Preserve READY status for online serving during re-indexing
                if doc.status != DocumentStatus.READY:
                    doc.status = DocumentStatus.VECTOR_SYNC
                    await session.commit()
            except Exception as dispatch_exc:
                logger.error("Failed to dispatch vector sync task to broker", document_id=str(doc.id), error=str(dispatch_exc))
                await PipelineFailureSynchronizer.record_pipeline_failure(
                    session=session,
                    document_id=doc.id,
                    failing_stage="vector_sync_dispatch",
                    error_code="BROKER_DISPATCH_FAILED",
                    error_message=f"Broker dispatch failed: {dispatch_exc!s}",
                    exception=dispatch_exc,
                    tenant_id=doc.tenant_id,
                    version_id=target_ver_uuid,
                )
    except Exception as e:
        logger.error("Pipeline Orchestrator: Failed to handle embedding completed", error=str(e))

async def handle_vector_sync_completed(event) -> None:
    """Mark document as READY and clean up superseded version vectors."""
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
            from sqlalchemy import select
            stmt = select(Document).where(Document.id == uuid.UUID(str(doc_id))).with_for_update()
            res = await session.execute(stmt)
            doc = res.scalar_one_or_none()
            if not doc:
                return

            event_data = getattr(event, "data", {}) if isinstance(getattr(event, "data", None), dict) else {}
            payload_obj = getattr(event, "payload", None)

            target_ver_id = (
                event_data.get("document_version_id")
                or event_data.get("version_id")
                or (getattr(payload_obj, "document_version_id", None) if payload_obj else None)
                or (getattr(payload_obj, "version_id", None) if payload_obj else None)
                or doc.latest_version_id
            )

            if target_ver_id and isinstance(target_ver_id, (str, uuid.UUID)):
                from backend.document.models.document import DocumentVersion
                from backend.document.repositories.document_repository import DocumentRepository
                doc_repo = DocumentRepository()
                target_ver_uuid = uuid.UUID(str(target_ver_id))

                # P0-3F: Monotonic Version Check
                target_version = await session.get(DocumentVersion, target_ver_uuid)
                current_latest_version = (
                    await session.get(DocumentVersion, doc.latest_version_id)
                    if doc.latest_version_id else None
                )

                if (
                    current_latest_version is None
                    or (target_version and target_version.version_number >= current_latest_version.version_number)
                ):
                    # Monotonic progression: target version is current or newer
                    await doc_repo.set_active_version(doc.id, target_ver_uuid, session)
                    doc.latest_version_id = target_ver_uuid
                    doc.status = DocumentStatus.READY
                    logger.info(
                        "Promoted document active version",
                        document_id=str(doc.id),
                        version_id=str(doc.latest_version_id),
                        version_number=target_version.version_number if target_version else 1,
                    )
                else:
                    # Out-of-order arrival: older version completed vector sync after a newer version was already activated
                    logger.warning(
                        "Superseded version arrived out of order; retaining newer active version",
                        document_id=str(doc.id),
                        stale_version_id=str(target_ver_uuid),
                        stale_version_number=target_version.version_number if target_version else 0,
                        active_version_id=str(doc.latest_version_id),
                        active_version_number=current_latest_version.version_number,
                    )
                    # Ensure stale version vectors are marked inactive
                    if target_version:
                        target_version.is_active_vector = False
            else:
                doc.status = DocumentStatus.READY

            await session.commit()
            logger.info("Document is now READY for RAG with active version", document_id=str(doc.id), version_id=str(doc.latest_version_id))

            # Milestone 4 (AUD-007): Purge superseded vector points strictly AFTER active version promotion commits.
            try:
                from backend.modules.vector.services.vector_service import VectorStorageService
                vec_svc = VectorStorageService(session=session)
                await vec_svc.cleanup_old_versions_vectors(
                    document_id=doc.id,
                    current_version_id=doc.latest_version_id,
                    tenant_id=doc.tenant_id,
                )
                await session.commit()
            except Exception as cleanup_err:
                logger.error(
                    "Pipeline Orchestrator: Post-promotion vector cleanup failed",
                    document_id=str(doc.id),
                    version_id=str(doc.latest_version_id),
                    error=str(cleanup_err),
                )
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
