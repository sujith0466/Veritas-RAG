"""Celery Chunking Worker (`process_document_chunking_task`).

Runs asynchronous chunking pipeline on the dedicated `ingestion` queue.
Executes text splitting, doubly-linked sequence linking, quota verification, batch persistence,
and emits `DocumentChunked` domain events with exponential backoff retry for `RECOVERABLE` errors.
"""

import asyncio
import uuid
from typing import Any

import structlog

from backend.database.engine import get_session_factory
from backend.document.models import DocumentEventLog
from backend.modules.chunking.events import (EVENT_CHUNKING_FAILED,
                                             create_chunk_event)
from backend.modules.chunking.schemas.errors import (ErrorSeverity,
                                                     get_error_severity)
from backend.modules.chunking.services.chunk_service import ChunkingService
from backend.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, queue="ingestion", max_retries=3, acks_late=True)
def process_document_chunking_task(
    self: Any,
    tenant_id: str,
    document_id: str,
    version_id: str,
    strategy_override: str | None = None,
    max_characters: int = 1000,
    overlap_characters: int = 200,
) -> dict[str, Any]:
    """Background Celery task executing document chunking.

    Args:
        tenant_id: Tenant namespace.
        document_id: String UUID of Document.
        version_id: String UUID of DocumentVersion.
        strategy_override: Optional strategy code.
        max_characters: Max chars per chunk.
        overlap_characters: Overlap chars.

    Returns:
        Dictionary summary of execution outcome.
    """
    return asyncio.run(
        _async_process_chunking(
            self,
            tenant_id,
            uuid.UUID(document_id),
            uuid.UUID(version_id),
            strategy_override,
            max_characters,
            overlap_characters,
        )
    )


async def _async_process_chunking(
    task_instance: Any,
    tenant_id: str,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    strategy_override: str | None,
    max_characters: int,
    overlap_characters: int,
) -> dict[str, Any]:
    session_factory = get_session_factory()
    service = ChunkingService()

    async with session_factory() as session:
        try:
            chunks, duration_ms = await service.chunk_document_version(
                tenant_id=tenant_id,
                document_id=document_id,
                version_id=version_id,
                session=session,
                strategy_override=strategy_override,
                max_characters=max_characters,
                overlap_characters=overlap_characters,
            )
            await session.commit()
            logger.info(
                "chunking_task_completed",
                tenant_id=tenant_id,
                document_id=str(document_id),
                chunk_count=len(chunks),
                duration_ms=duration_ms,
            )
            return {
                "status": "success",
                "document_id": str(document_id),
                "version_id": str(version_id),
                "chunk_count": len(chunks),
                "duration_ms": duration_ms,
            }

        except Exception as exc:
            await session.rollback()
            error_code = getattr(exc, "code", "CHK_003")
            severity = getattr(exc, "severity", get_error_severity(str(error_code)))

            logger.error(
                "chunking_task_failed",
                tenant_id=tenant_id,
                document_id=str(document_id),
                error_code=str(error_code),
                severity=str(severity),
                error=str(exc),
            )

            # Record failure event if possible
            try:
                fail_event = create_chunk_event(
                    event_type=EVENT_CHUNKING_FAILED,
                    tenant_id=tenant_id,
                    document_id=document_id,
                    document_version_id=version_id,
                    data={
                        "error_code": str(error_code),
                        "message": str(exc),
                        "severity": str(severity),
                    },
                )
                event_log = DocumentEventLog(
                    document_id=document_id,
                    event_type=EVENT_CHUNKING_FAILED,
                    payload=fail_event.model_dump(),
                )
                session.add(event_log)
                await session.commit()
            except Exception as log_exc:
                logger.warning("failed_to_log_chunking_error_event", error=str(log_exc))

            if (
                severity == ErrorSeverity.RECOVERABLE
                and task_instance.request.retries < task_instance.max_retries
            ):
                backoff_seconds = 2**task_instance.request.retries * 5
                raise task_instance.retry(exc=exc, countdown=backoff_seconds)

            raise exc
