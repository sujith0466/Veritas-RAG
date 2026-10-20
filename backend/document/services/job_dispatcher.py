"""Resilient Background Job Dispatcher.

Provides durable dispatch tracking, deduplication, and observable failure state management
for Celery pipeline execution without silent exception suppression.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from backend.document.models.job import DispatchState, ProcessingJob

logger = structlog.get_logger(__name__)

DISPATCH_COOLDOWN_SECONDS = 60


@dataclass(frozen=True)
class DispatchResult:
    """Summary of a background job dispatch attempt."""

    success: bool
    task_id: str | None = None
    dispatch_state: str = DispatchState.PENDING_DISPATCH.value
    error: str | None = None
    deduplicated: bool = False


class JobDispatcher:
    """Handles reliable, deduplicated dispatch of document processing jobs to Celery."""

    @staticmethod
    def dispatch_job_sync(
        job: ProcessingJob,
        session: Session | None = None,
        queue: str = "ingestion",
        force: bool = False,
        correlation_id: str | None = None,
    ) -> DispatchResult:
        """Synchronous version of job dispatch for sync contexts (e.g. Celery sweeper or sync tasks)."""
        return JobDispatcher._execute_dispatch(
            job, session=session, queue=queue, force=force, correlation_id=correlation_id
        )

    @staticmethod
    async def dispatch_job(
        job: ProcessingJob,
        session: AsyncSession | None = None,
        queue: str = "ingestion",
        force: bool = False,
        correlation_id: str | None = None,
    ) -> DispatchResult:
        """Asynchronously dispatch a processing job to Celery broker with durable state tracking.
        
        Args:
            job: The ProcessingJob ORM instance to dispatch.
            session: Optional AsyncSession to persist immediate dispatch metadata.
            queue: Celery queue name (default: "ingestion").
            force: Bypass deduplication and cooldown checks if True.
            correlation_id: Optional correlation ID for distributed trace continuity.
        """
        result = JobDispatcher._execute_dispatch(
            job, session=session, queue=queue, force=force, correlation_id=correlation_id
        )
        if session:
            try:
                await session.flush()
            except Exception as flush_err:
                logger.warning(
                    "Failed to flush dispatch state update",
                    job_id=str(job.id),
                    error=str(flush_err),
                )
        return result

    @staticmethod
    def _execute_dispatch(
        job: ProcessingJob,
        session: Session | AsyncSession | None = None,
        queue: str = "ingestion",
        force: bool = False,
        correlation_id: str | None = None,
    ) -> DispatchResult:
        """Internal dispatch execution engine with deduplication and error recording."""
        now = datetime.now(timezone.utc)

        # Resolve correlation ID from parameter or active context
        resolved_correlation_id = correlation_id
        if not resolved_correlation_id:
            try:
                import structlog.contextvars
                resolved_correlation_id = structlog.contextvars.get_contextvars().get("correlation_id")
            except Exception:
                resolved_correlation_id = None

        # 1. Deduplication Guard: Check if already DISPATCHED and active or within cooldown
        if not force and job.dispatch_state == DispatchState.DISPATCHED.value:
            if job.dispatched_at:
                elapsed = (now - job.dispatched_at).total_seconds()
                if elapsed < DISPATCH_COOLDOWN_SECONDS:
                    logger.info(
                        "Dispatch deduplicated: job recently dispatched",
                        job_id=str(job.id),
                        elapsed_seconds=elapsed,
                        task_id=job.celery_task_id,
                    )
                    return DispatchResult(
                        success=True,
                        task_id=job.celery_task_id,
                        dispatch_state=job.dispatch_state,
                        deduplicated=True,
                    )

        # 2. Prevent redispatching jobs that are already in active processing
        active_statuses = {
            "CLAIMED",
            "PROCESSING",
            "VALIDATING",
            "EXTRACTING",
            "OCR",
            "CHUNKING",
            "EMBEDDING",
            "VECTOR_SYNC",
            "READY",
        }
        if not force and job.status in active_statuses:
            logger.info(
                "Dispatch skipped: job already active or terminal",
                job_id=str(job.id),
                status=job.status,
            )
            return DispatchResult(
                success=True,
                task_id=job.celery_task_id,
                dispatch_state=job.dispatch_state,
                deduplicated=True,
            )

        # 3. Mark intent
        job.dispatch_state = DispatchState.PENDING_DISPATCH.value

        # 4. Attempt Celery broker dispatch
        try:
            from backend.document.workers.ingestion import process_document_job

            task_headers = {}
            if resolved_correlation_id:
                task_headers["correlation_id"] = resolved_correlation_id

            task = process_document_job.apply_async(
                args=[str(job.id)],
                queue=queue,
                headers=task_headers if task_headers else None,
            )
            job.dispatch_state = DispatchState.DISPATCHED.value
            job.celery_task_id = str(task.id) if task else None
            job.dispatched_at = now
            job.dispatch_error = None

            logger.info(
                "Successfully dispatched processing job to Celery",
                job_id=str(job.id),
                task_id=job.celery_task_id,
                queue=queue,
                correlation_id=resolved_correlation_id,
            )
            return DispatchResult(
                success=True,
                task_id=job.celery_task_id,
                dispatch_state=DispatchState.DISPATCHED.value,
            )
        except Exception as exc:
            # 5. Record observable failure without swallowing
            error_message = f"{type(exc).__name__}: {str(exc)}"
            job.dispatch_state = DispatchState.FAILED_DISPATCH.value
            job.dispatch_error = error_message
            job.dispatched_at = now

            logger.error(
                "Failed to dispatch processing job to broker",
                job_id=str(job.id),
                queue=queue,
                error=error_message,
                correlation_id=resolved_correlation_id,
            )
            return DispatchResult(
                success=False,
                error=error_message,
                dispatch_state=DispatchState.FAILED_DISPATCH.value,
            )
