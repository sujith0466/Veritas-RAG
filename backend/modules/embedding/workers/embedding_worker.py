"""Celery Embedding Worker Orchestrator (`CeleryEmbeddingWorker`).

Encapsulates database session handling, retry calculations (`jittered exponential backoff`),
and progress reporting for async Celery task execution (`ADR-M2-003`).
"""

import random
import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.events.dispatcher import get_dispatcher
from backend.modules.embedding.repositories.embedding_repository import \
    EmbeddingRepository
from backend.modules.embedding.schemas.errors import (ErrorSeverity,
                                                      get_error_severity)
from backend.modules.embedding.services.embedding_service import \
    EmbeddingService

logger = structlog.get_logger(__name__)


class CeleryEmbeddingWorker:
    """Orchestrates `EmbeddingService` execution within Celery worker tasks."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = EmbeddingRepository(session)
        self.event_dispatcher = get_dispatcher()
        self.service = EmbeddingService(self.repository, self.event_dispatcher)

    @staticmethod
    def calculate_jittered_backoff(
        retry_count: int, base_seconds: float = 5.0, max_seconds: float = 300.0
    ) -> float:
        """Compute exponential backoff with full jitter to avoid API thundering herds."""
        exponential = min(max_seconds, base_seconds * (2**retry_count))
        jitter = random.uniform(1.0, 5.0)
        return round(min(max_seconds, exponential + jitter), 2)

    async def execute_batch(
        self,
        celery_task: Any,
        job_id: uuid.UUID,
        tenant_id: str,
        batch_size: int = 100,
        force_reembed: bool = False,
    ) -> dict[str, Any]:
        """Execute batch vectorization and report status / retries."""
        try:
            job = await self.service.process_embedding_batch(
                job_id=job_id,
                tenant_id=tenant_id,
                batch_size=batch_size,
                force_reembed=force_reembed,
            )
            await self.session.commit()

            if celery_task and hasattr(celery_task, "update_state"):
                celery_task.update_state(
                    state="SUCCESS",
                    meta={
                        "job_id": str(job.id),
                        "processed": job.processed_chunks,
                        "total": job.total_chunks,
                        "tokens": job.total_tokens_consumed,
                    },
                )
                
            from backend.core.events.types import EventType
            from backend.core.events.dispatcher import get_dispatcher
            from backend.modules.embedding.events import create_embedding_event
            
            success_event = create_embedding_event(
                event_type=EventType.EMBEDDING_COMPLETED,
                tenant_id=tenant_id,
                job_id=job.id,
                document_id=job.document_id,
                data={
                    "processed_chunks": job.processed_chunks,
                    "tokens_consumed": job.total_tokens_consumed,
                }
            )
            dispatcher = get_dispatcher()
            await dispatcher.publish(success_event)

            return {
                "status": "success",
                "job_id": str(job.id),
                "processed_chunks": job.processed_chunks,
                "total_chunks": job.total_chunks,
                "tokens_consumed": job.total_tokens_consumed,
            }
        except Exception as exc:
            await self.session.rollback()
            error_code = getattr(exc, "code", "EMB_004")
            severity = getattr(exc, "severity", get_error_severity(str(error_code)))

            logger.error(
                "celery_embedding_worker_failed",
                job_id=str(job_id),
                tenant_id=tenant_id,
                error_code=str(error_code),
                severity=str(severity),
                error=str(exc),
            )

            # Check if Celery retry is appropriate and supported
            if (
                celery_task
                and hasattr(celery_task, "request")
                and hasattr(celery_task, "retry")
            ):
                retries = getattr(celery_task.request, "retries", 0)
                max_retries = getattr(celery_task, "max_retries", 3)

                if severity == ErrorSeverity.RECOVERABLE and retries < max_retries:
                    countdown = self.calculate_jittered_backoff(retries)
                    logger.warning(
                        "celery_embedding_worker_retrying",
                        job_id=str(job_id),
                        retry=retries + 1,
                        countdown=countdown,
                    )
                    raise celery_task.retry(exc=exc, countdown=countdown)

            raise exc
