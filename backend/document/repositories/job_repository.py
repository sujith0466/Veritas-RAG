"""Processing job persistence repository (`JobRepository`).

Isolates database tracking for background pipeline tasks, step updates, and retry counts.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
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
