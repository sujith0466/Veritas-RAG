"""Processing job persistence repository (`JobRepository`).

Isolates database tracking for background pipeline tasks, step updates, and retry counts.
"""

from datetime import UTC, datetime
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.models.job import ProcessingJob


class JobRepository:
    """Repository for CRUD operations on ProcessingJob entities."""

    async def create(self, job: ProcessingJob, session: AsyncSession) -> ProcessingJob:
        """Persist a new ProcessingJob to the database."""
        if not job.started_at:
            job.started_at = datetime.now(UTC)
        session.add(job)
        await session.flush()
        await session.refresh(job)
        return job

    async def get_by_id(
        self, job_id: uuid.UUID, session: AsyncSession
    ) -> ProcessingJob | None:
        """Fetch a ProcessingJob by its unique ID."""
        stmt = select(ProcessingJob).where(
            ProcessingJob.id == job_id, ProcessingJob.is_deleted.is_(False)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_document_id(
        self, document_id: uuid.UUID, session: AsyncSession
    ) -> ProcessingJob | None:
        """Fetch the most recent ProcessingJob for a given document."""
        stmt = (
            select(ProcessingJob)
            .where(
                ProcessingJob.document_id == document_id,
                ProcessingJob.is_deleted.is_(False),
            )
            .order_by(ProcessingJob.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_step(
        self,
        job_id: uuid.UUID,
        step: str,
        status: str,
        session: AsyncSession,
    ) -> ProcessingJob | None:
        """Update active processing step and overall status."""
        job = await self.get_by_id(job_id, session)
        if job:
            job.current_step = step
            job.status = status
            if status in {"COMPLETED", "FAILED"}:
                job.completed_at = datetime.now(UTC)
            await session.flush()
            await session.refresh(job)
        return job

    async def record_error(
        self,
        job_id: uuid.UUID,
        error_code: str,
        error_message: str,
        session: AsyncSession,
        increment_retry: bool = False,
    ) -> ProcessingJob | None:
        """Record an error during pipeline processing and optionally increment retry count."""
        job = await self.get_by_id(job_id, session)
        if job:
            job.error_code = error_code
            job.error_message = error_message
            if increment_retry:
                job.retry_count += 1
            await session.flush()
            await session.refresh(job)
        return job

    async def get_by_idempotency_key(
        self, key: str, session: AsyncSession
    ) -> ProcessingJob | None:
        """Fetch a ProcessingJob by its unique idempotency key."""
        stmt = select(ProcessingJob).where(
            ProcessingJob.idempotency_key == key,
            ProcessingJob.is_deleted.is_(False),
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_dlq_jobs(
        self,
        tenant_id: str | None,
        page: int,
        size: int,
        session: AsyncSession,
        error_code: str | None = None,
    ) -> list[ProcessingJob]:
        """Fetch Dead Letter Queue jobs with optional tenant and error code filtering."""
        from backend.document.models.document import Document

        stmt = (
            select(ProcessingJob)
            .join(Document, ProcessingJob.document_id == Document.id)
            .where(
                ProcessingJob.status == "DLQ",
                ProcessingJob.is_deleted.is_(False),
                Document.is_deleted.is_(False),
            )
        )
        if tenant_id:
            stmt = stmt.where(Document.tenant_id == tenant_id)
        if error_code:
            stmt = stmt.where(ProcessingJob.error_code == error_code)

        stmt = (
            stmt.order_by(ProcessingJob.dlq_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def reset_job_for_retry(
        self,
        job_id: uuid.UUID,
        session: AsyncSession,
        resume_from_step: str | None = None,
    ) -> ProcessingJob | None:
        """Reset a failed or DLQ job to QUEUED state for operator retry."""
        job = await self.get_by_id(job_id, session)
        if not job:
            return None

        job.status = "QUEUED"
        job.retry_count = 0
        job.dlq_reason = None
        job.dlq_at = None
        job.error_code = None
        job.error_message = None
        if resume_from_step:
            job.resume_from_step = resume_from_step
            job.current_step = resume_from_step

        await session.flush()
        await session.refresh(job)
        return job

    async def bulk_update_status(
        self, job_ids: list[uuid.UUID], status: str, session: AsyncSession
    ) -> int:
        """Update status for multiple jobs."""
        if not job_ids:
            return 0
        stmt = (
            update(ProcessingJob)
            .where(ProcessingJob.id.in_(job_ids))
            .values(status=status, updated_at=datetime.now(UTC))
        )
        result = await session.execute(stmt)
        return result.rowcount

    async def get_stale_claimed_jobs(
        self, threshold_minutes: int, session: AsyncSession
    ) -> list[ProcessingJob]:
        """Find jobs that were claimed long ago and might be stale."""
        # This will be used in conjunction with a Redis check in the service layer
        from datetime import timedelta
        threshold = datetime.now(UTC) - timedelta(minutes=threshold_minutes)
        stmt = select(ProcessingJob).where(
            ProcessingJob.status == "CLAIMED",
            ProcessingJob.claimed_at < threshold,
            ProcessingJob.is_deleted.is_(False),
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_for_escalation(
        self, priority: int, age_hours: int, session: AsyncSession
    ) -> list[ProcessingJob]:
        """Find pending/queued jobs of a certain priority that are older than age_hours."""
        from datetime import timedelta
        threshold = datetime.now(UTC) - timedelta(hours=age_hours)
        stmt = select(ProcessingJob).where(
            ProcessingJob.status.in_(["PENDING", "QUEUED"]),
            ProcessingJob.priority == priority,
            ProcessingJob.created_at < threshold,
            ProcessingJob.is_deleted.is_(False),
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
