"""Celery Embedding Task (`process_embedding_batch_task`).

Runs asynchronous batch vectorization on the `embeddings` queue (`ADR-M2-003`).
Invokes `CeleryEmbeddingWorker` to handle session management, progress state, and retry logic.
"""

import asyncio
import uuid
from typing import Any

import structlog

from backend.database.engine import get_session_factory
from backend.modules.embedding.workers.embedding_worker import \
    CeleryEmbeddingWorker
from backend.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, queue="embeddings", max_retries=3, acks_late=True)
def process_embedding_batch_task(
    self: Any,
    job_id: str,
    tenant_id: str,
    batch_size: int = 100,
    force_reembed: bool = False,
) -> dict[str, Any]:
    """Background Celery task for processing an `EmbeddingJob` across chunk batches.

    Args:
        job_id: String UUID of the `EmbeddingJob`.
        tenant_id: Tenant namespace identifier.
        batch_size: Number of chunks per sub-batch (default: 100).
        force_reembed: Whether to bypass zero-call idempotency cache (default: False).

    Returns:
        Dictionary summary containing processed chunk count and token usage.
    """
    return asyncio.run(
        _async_process_embedding_task(
            self,
            uuid.UUID(job_id),
            tenant_id,
            batch_size,
            force_reembed,
        )
    )


async def _async_process_embedding_task(
    task_instance: Any,
    job_id: uuid.UUID,
    tenant_id: str,
    batch_size: int,
    force_reembed: bool,
) -> dict[str, Any]:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from backend.core.config import get_settings
    
    settings = get_settings().database
    engine = create_async_engine(settings.url, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    
    try:
        async with session_factory() as session:
            worker = CeleryEmbeddingWorker(session)
            return await worker.execute_batch(
                celery_task=task_instance,
                job_id=job_id,
                tenant_id=tenant_id,
                batch_size=batch_size,
                force_reembed=force_reembed,
            )
    finally:
        await engine.dispose()
