"""Processing Job Service (`ProcessingJobService`).

Orchestrates the lifecycle, queue transitions, step metrics, and distributed locking
for the background job pipeline.
"""

from datetime import UTC, datetime
import hashlib
import traceback
from typing import Any
import uuid

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.cache.locks import LockAcquisitionError, acquire_lock
from backend.document.models.document import Document
from backend.document.models.failed_job import FailedJobDiagnostics
from backend.document.models.job import ProcessingJob
from backend.document.models.job_step import ProcessingJobStep
from backend.document.models.status import DocumentStatus
from backend.document.repositories.failed_job_repository import FailedJobRepository
from backend.document.repositories.job_audit_repository import JobAuditRepository
from backend.document.repositories.job_repository import JobRepository
from backend.document.repositories.job_step_repository import JobStepRepository
from backend.document.schemas.errors import DocumentDomainException


class ProcessingJobService:
    """Service layer for ProcessingJob lifecycle management."""

    def __init__(
        self,
        job_repo: JobRepository,
        step_repo: JobStepRepository,
        audit_repo: JobAuditRepository,
        redis_client: redis.Redis,
        failed_job_repo: FailedJobRepository | None = None,
    ):
        self.job_repo = job_repo
        self.step_repo = step_repo
        self.audit_repo = audit_repo
        self.redis = redis_client
        self.failed_job_repo = failed_job_repo or FailedJobRepository()

    async def enqueue_job(
        self,
        document_id: uuid.UUID,
        priority: int,
        started_at: datetime | None,
        actor: str,
        session: AsyncSession,
        batch_id: uuid.UUID | None = None,
        version_id: uuid.UUID | None = None,
    ) -> ProcessingJob:
        """Enqueue a new processing job with idempotency protection."""
        # Generate idempotency key based on doc ID, version, and date to prevent duplicate enqueues
        raw_key = f"{document_id}_{version_id}_{datetime.now(UTC).date().isoformat()}"
        idempotency_key = hashlib.sha256(raw_key.encode()).hexdigest()

        # Check existing
        existing = await self.job_repo.get_by_idempotency_key(idempotency_key, session)
        if existing and existing.status in {"PENDING", "QUEUED", "CLAIMED", "COMPLETED"}:
            return existing

        job = ProcessingJob(
            document_id=document_id,
            batch_id=batch_id,
            version_id=version_id,
            status="PENDING",
            current_step="upload",
            priority=priority,
            started_at=started_at or datetime.now(UTC),
            idempotency_key=idempotency_key,
        )
        job = await self.job_repo.create(job, session)

        await self.audit_repo.append(
            job.id, "JOB_ENQUEUED", actor, {"priority": priority}, session
        )

        return job

    async def claim_job(
        self,
        job_id: uuid.UUID,
        worker_id: str,
        session: AsyncSession,
    ) -> ProcessingJob | None:
        """Claim a job for processing, using a Redis distributed lock."""
        lock_key = f"job_lock:{job_id}"

        try:
            async with acquire_lock(lock_key, timeout=60, acquire_timeout=2) as _lock:
                job = await self.job_repo.get_by_id(job_id, session)
                if not job or job.status not in {"PENDING", "QUEUED", "DLQ"}:
                    return None

            job.status = "CLAIMED"
            job.claimed_at = datetime.now(UTC)
            job.claimed_by_worker = worker_id
            await session.flush()

            await self.audit_repo.append(
                job.id, "JOB_CLAIMED", worker_id, {"worker_id": worker_id}, session
            )
            return job
        except LockAcquisitionError:
            return None

    async def start_step(
        self,
        job_id: uuid.UUID,
        step_name: str,
        worker_id: str,
        session: AsyncSession,
    ) -> ProcessingJobStep:
        """Start a new granular step for a job."""
        job = await self.job_repo.get_by_id(job_id, session)
        if not job:
            raise DocumentDomainException(f"Job {job_id} not found", 404)

        job.current_step = step_name
        job.status = "PROCESSING"
        await session.flush()

        step = await self.step_repo.create_step(job_id, step_name, session)
        await self.audit_repo.append(
            job_id, "STEP_STARTED", worker_id, {"step_name": step_name}, session
        )
        return step

    async def complete_step(
        self,
        job_id: uuid.UUID,
        step_name: str,
        worker_id: str,
        metrics: dict[str, Any],
        session: AsyncSession,
    ) -> None:
        """Complete a granular step and update job metrics."""
        step = await self.step_repo.get_step(job_id, step_name, session)
        if not step:
            raise DocumentDomainException(f"Step {step_name} for job {job_id} not found", 404)

        duration_ms = (datetime.now(UTC) - step.started_at).total_seconds() * 1000

        await self.step_repo.update_step_status(
            step.id, "COMPLETED", duration_ms, None, None, session
        )

        job = await self.job_repo.get_by_id(job_id, session)
        if job:
            if not job.step_metrics:
                job.step_metrics = {}
            job.step_metrics[step_name] = metrics
            await session.flush()

        await self.audit_repo.append(
            job_id,
            "STEP_COMPLETED",
            worker_id,
            {"step_name": step_name, "duration_ms": duration_ms, "metrics": metrics},
            session,
        )

    async def record_step_error(
        self,
        job_id: uuid.UUID,
        step_name: str,
        worker_id: str,
        error_code: str,
        error_message: str,
        is_fatal: bool,
        session: AsyncSession,
        stack_trace: str | None = None,
        worker_context: dict[str, Any] | None = None,
        payload_snapshot: dict[str, Any] | None = None,
    ) -> None:
        """Record an error for a step. If fatal or max retries reached, move to DLQ with diagnostics."""
        step = await self.step_repo.get_step(job_id, step_name, session)
        if step:
            await self.step_repo.update_step_status(
                step.id, "FAILED", None, error_code, {"message": error_message}, session
            )

        job = await self.job_repo.get_by_id(job_id, session)
        if not job:
            return

        job.retry_count += 1

        if is_fatal or job.retry_count >= job.max_retries:
            job.status = "DLQ"
            job.dlq_reason = f"[{step_name}] {error_code}: {error_message}"
            job.dlq_at = datetime.now(UTC)
            job.error_code = error_code
            job.error_message = error_message

            # Fetch tenant_id from associated document
            doc_stmt = select(Document).where(Document.id == job.document_id)
            doc_res = await session.execute(doc_stmt)
            doc = doc_res.scalar_one_or_none()
            tenant_id = doc.tenant_id if doc else "unknown"

            if doc:
                doc.status = DocumentStatus.FAILED
                doc.error_code = error_code
                doc.error_message = error_message

            # Create forensic diagnostics snapshot
            diagnostics = FailedJobDiagnostics(
                job_id=job.id,
                tenant_id=tenant_id,
                failing_step=step_name,
                exception_class=error_code,
                stack_trace=stack_trace or "".join(traceback.format_stack()),
                worker_context=worker_context or {"worker_id": worker_id},
                payload_snapshot=payload_snapshot or {"step_metrics": job.step_metrics},
                remediation_status="PENDING_TRIAGE",
            )
            await self.failed_job_repo.create_diagnostics(diagnostics, session)

            await self.audit_repo.append(
                job_id, "JOB_DLQ", worker_id, {"reason": job.dlq_reason, "error_code": error_code}, session
            )
        else:
            job.status = "QUEUED"
            await self.audit_repo.append(
                job_id, "STEP_FAILED_RETRY", worker_id, {"step": step_name, "error": error_message, "retry_count": job.retry_count}, session
            )

        await session.flush()

    async def mark_job_completed(
        self,
        job_id: uuid.UUID,
        worker_id: str,
        session: AsyncSession,
    ) -> None:
        """Mark the overall job as fully completed and update document status."""
        job = await self.job_repo.get_by_id(job_id, session)
        if not job:
            return

        job.status = "COMPLETED"
        job.completed_at = datetime.now(UTC)

        # Update document status to READY
        doc_stmt = select(Document).where(Document.id == job.document_id)
        doc_res = await session.execute(doc_stmt)
        doc = doc_res.scalar_one_or_none()
        if doc:
            doc.status = DocumentStatus.READY

        await session.flush()

        await self.audit_repo.append(
            job_id, "JOB_COMPLETED", worker_id, None, session
        )

    async def requeue_stale_jobs(
        self,
        threshold_minutes: int,
        session: AsyncSession,
    ) -> int:
        """Find stale claimed jobs and requeue them (for cron worker)."""
        stale_jobs = await self.job_repo.get_stale_claimed_jobs(threshold_minutes, session)
        if not stale_jobs:
            return 0

        requeued_count = 0
        for job in stale_jobs:
            # Check redis if worker is still holding lock / heartbeating
            lock_key = f"job_lock:{job.id}"
            is_locked = await self.redis.exists(lock_key)
            if not is_locked:
                job.status = "QUEUED"
                job.claimed_by_worker = None
                job.claimed_at = None
                await self.audit_repo.append(
                    job.id, "JOB_REQUEUED_STALE", "system_cron", None, session
                )
                requeued_count += 1

        await session.flush()
        return requeued_count
