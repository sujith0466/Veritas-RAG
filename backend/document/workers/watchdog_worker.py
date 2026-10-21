"""Document Pipeline Watchdog Worker.

Celery Beat watchdog task sweeping documents stuck in CHUNKING, EMBEDDING, or VECTOR_SYNC (ARCH-005).
"""

from datetime import UTC, datetime, timedelta
import uuid

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.cache.client import get_redis_client
from backend.database.engine import get_session_factory
from backend.document.models.document import Document, DocumentStatus
from backend.document.models.job import ProcessingJob
from backend.document.services.failure_service import PipelineFailureSynchronizer
from backend.modules.embedding.models.embedding_job import EmbeddingJob

logger = structlog.get_logger(__name__)


async def sweep_stale_pipeline_documents(
    stale_threshold_minutes: int = 15,
    max_age_hours: int = 24,
    session: AsyncSession | None = None,
    redis_client = None,
) -> int:
    """Identify documents stuck in non-terminal processing states and apply safe recovery (ARCH-005).

    Handles documents stuck in CHUNKING, EMBEDDING, or VECTOR_SYNC states:
    - Verifies active distributed task locks (vector sync, embedding job, chunking) to prevent race conditions.
    - If retries remain on the active processing job: re-dispatches the stuck stage with correct queues and contracts.
    - If retries are exhausted (or no job found): transitions to terminal FAILED via PipelineFailureSynchronizer
      with error_code='STUCK_PIPELINE_TIMEOUT', enabling the user to retry the document.
    """
    if session is None:
        return 0

    redis = redis_client if redis_client is not None else get_redis_client()

    # 1. Acquire distributed lock to prevent concurrent watchdog execution
    lock_key = "cron_lock:sweep_stale_pipeline_documents"
    lock_acquired = False
    if redis is not None:
        try:
            lock_res = await redis.set(lock_key, "locked", ex=120, nx=True)
            if not lock_res:
                logger.info("Concurrent pipeline watchdog execution skipped due to active lock")
                return 0
            lock_acquired = True
        except Exception as lock_err:
            logger.warning("Redis lock acquisition failed for watchdog, safely aborting sweep", error=str(lock_err))
            return 0

    handled_count = 0
    now = datetime.now(UTC)
    threshold_dt = now - timedelta(minutes=stale_threshold_minutes)
    oldest_dt = now - timedelta(hours=max_age_hours) if max_age_hours else None

    try:
        # 2. Query for documents stuck in CHUNKING, EMBEDDING, or VECTOR_SYNC
        stuck_statuses = [
            DocumentStatus.CHUNKING,
            DocumentStatus.EMBEDDING,
            DocumentStatus.VECTOR_SYNC,
        ]

        stmt = (
            select(Document)
            .where(
                Document.status.in_(stuck_statuses),
                Document.is_deleted.is_(False),
                Document.updated_at <= threshold_dt,
            )
        )
        if oldest_dt:
            stmt = stmt.where(Document.updated_at >= oldest_dt)

        result = await session.execute(stmt)
        stuck_docs = list(result.scalars().all())

        for doc in stuck_docs:
            doc_id_str = str(doc.id)
            doc_status_val = doc.status.value if hasattr(doc.status, "value") else str(doc.status)
            version_id_str = str(doc.latest_version_id) if doc.latest_version_id else ""

            # Fetch active EmbeddingJob if in EMBEDDING stage
            emb_job = None
            if doc_status_val == DocumentStatus.EMBEDDING.value:
                emb_stmt = (
                    select(EmbeddingJob)
                    .where(
                        EmbeddingJob.document_id == doc.id,
                        EmbeddingJob.tenant_id == doc.tenant_id,
                        EmbeddingJob.is_deleted.is_(False),
                    )
                    .order_by(EmbeddingJob.created_at.desc())
                    .limit(1)
                )
                emb_job = (await session.execute(emb_stmt)).scalar_one_or_none()

            # Check if active task lock exists in Redis
            if redis is not None:
                try:
                    # Stage-specific worker lock detection:
                    if doc_status_val == DocumentStatus.VECTOR_SYNC.value and version_id_str:
                        if await redis.exists(f"lock:vector:sync:{version_id_str}"):
                            logger.info("Vector sync worker lock is active; skipping watchdog sweep", document_id=doc_id_str, version_id=version_id_str)
                            continue
                    elif doc_status_val == DocumentStatus.EMBEDDING.value and emb_job is not None:
                        if await redis.exists(f"lock:embedding:job:{emb_job.id}"):
                            logger.info("Embedding worker lock is active; skipping watchdog sweep", document_id=doc_id_str, job_id=str(emb_job.id))
                            continue
                    elif doc_status_val == DocumentStatus.CHUNKING.value and version_id_str:
                        if await redis.exists(f"lock:chunking:{version_id_str}"):
                            logger.info("Chunking worker lock is active; skipping watchdog sweep", document_id=doc_id_str, version_id=version_id_str)
                            continue

                    # Generic doc lock fallback
                    doc_lock = f"doc_lock:{doc_id_str}"
                    if await redis.exists(doc_lock):
                        logger.info("Document worker lock is active; skipping watchdog sweep", document_id=doc_id_str)
                        continue
                except Exception as lock_check_err:
                    logger.warning("Error checking worker locks in Redis, proceeding with caution", document_id=doc_id_str, error=str(lock_check_err))

            # Fetch active ProcessingJob
            job_stmt = (
                select(ProcessingJob)
                .where(
                    ProcessingJob.document_id == doc.id,
                    ProcessingJob.is_deleted.is_(False),
                )
                .order_by(ProcessingJob.created_at.desc())
                .limit(1)
            )
            job = (await session.execute(job_stmt)).scalar_one_or_none()

            can_retry = job is not None and (job.retry_count or 0) < (job.max_retries or 3)

            if can_retry:
                # Increment retry count
                previous_retry_count = job.retry_count or 0
                previous_status = job.status
                job.retry_count = previous_retry_count + 1
                job.status = "QUEUED"
                doc.updated_at = now
                session.add(job)
                session.add(doc)

                # Re-dispatch based on current stuck stage
                try:
                    if doc_status_val == DocumentStatus.VECTOR_SYNC.value:
                        from backend.modules.vector.workers.tasks import sync_vectors_to_qdrant_task
                        sync_vectors_to_qdrant_task.apply_async(
                            args=[doc_id_str, version_id_str, doc.tenant_id],
                            queue="indexing",
                        )
                    elif doc_status_val == DocumentStatus.EMBEDDING.value:
                        if emb_job is not None:
                            from backend.modules.embedding.workers.tasks import process_embedding_batch_task
                            process_embedding_batch_task.apply_async(
                                args=[str(emb_job.id), doc.tenant_id, 100, False],
                                queue="embeddings",
                            )
                        else:
                            from backend.modules.chunking.workers.tasks import process_document_chunking_task
                            process_document_chunking_task.apply_async(
                                args=[doc.tenant_id, doc_id_str, version_id_str],
                                queue="ingestion",
                            )
                    else:
                        from backend.modules.chunking.workers.tasks import process_document_chunking_task
                        process_document_chunking_task.apply_async(
                            args=[doc.tenant_id, doc_id_str, version_id_str],
                            queue="ingestion",
                        )
                    handled_count += 1
                    logger.info("Watchdog requeued stuck pipeline document", document_id=doc_id_str, stage=doc_status_val, retry=job.retry_count)
                except Exception as dispatch_err:
                    job.retry_count = previous_retry_count
                    job.status = previous_status
                    session.add(job)
                    logger.error("Watchdog redispatch failed", document_id=doc_id_str, error=str(dispatch_err))
            else:
                # Mark as FAILED via PipelineFailureSynchronizer (safe terminal recovery)
                stage_name = doc_status_val.lower()
                await PipelineFailureSynchronizer.record_pipeline_failure(
                    session=session,
                    document_id=doc.id,
                    failing_stage=stage_name,
                    error_code="STUCK_PIPELINE_TIMEOUT",
                    error_message=f"Document stuck in {doc_status_val} exceeding {stale_threshold_minutes}m threshold",
                    tenant_id=doc.tenant_id,
                    version_id=doc.latest_version_id,
                    job_id=job.id if job else None,
                    embedding_job_id=emb_job.id if emb_job else None,
                )
                handled_count += 1
                logger.warning(
                    "Watchdog marked stuck document as FAILED after retries exhausted",
                    document_id=doc_id_str,
                    stage=doc_status_val,
                )

        await session.flush()
    finally:
        if lock_acquired and redis is not None:
            try:
                await redis.delete(lock_key)
            except Exception:
                pass

    return handled_count


@shared_task(
    name="documents.sweep_stale_pipeline_documents",
    bind=True,
    ignore_result=True,
)
def sweep_stale_pipeline_documents_task(self):
    """Celery periodic task executing pipeline watchdog sweep."""
    import asyncio

    async def _run():
        session_factory = get_session_factory()
        async with session_factory() as session:
            count = await sweep_stale_pipeline_documents(stale_threshold_minutes=15, session=session)
            if count > 0:
                await session.commit()
                logger.info("Watchdog sweep recovered stuck pipeline documents", count=count)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(_run())
