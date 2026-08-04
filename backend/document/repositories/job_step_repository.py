"""Processing job step persistence repository (`JobStepRepository`).

Isolates database tracking for background pipeline task granular steps.
"""

from datetime import UTC, datetime
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.models.job_step import ProcessingJobStep


class JobStepRepository:
    """Repository for CRUD operations on ProcessingJobStep entities."""

    async def create_step(
        self, job_id: uuid.UUID, step_name: str, session: AsyncSession
    ) -> ProcessingJobStep:
        """Create a new job step."""
        step = ProcessingJobStep(
            job_id=job_id,
            step_name=step_name,
            step_status="RUNNING",
            started_at=datetime.now(UTC),
        )
        session.add(step)
        await session.flush()
        await session.refresh(step)
        return step

    async def get_step(
        self, job_id: uuid.UUID, step_name: str, session: AsyncSession
    ) -> ProcessingJobStep | None:
        """Fetch a specific step for a job."""
        stmt = select(ProcessingJobStep).where(
            ProcessingJobStep.job_id == job_id,
            ProcessingJobStep.step_name == step_name,
            ProcessingJobStep.is_deleted.is_(False),
        ).order_by(ProcessingJobStep.created_at.desc()).limit(1)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_step_status(
        self,
        step_id: uuid.UUID,
        status: str,
        duration_ms: float | None,
        error_code: str | None,
        error_detail: dict[str, Any] | None,
        session: AsyncSession,
    ) -> None:
        """Update a job step status."""
        values: dict[str, Any] = {
            "step_status": status,
            "updated_at": datetime.now(UTC),
        }
        if duration_ms is not None:
            values["duration_ms"] = duration_ms
        if error_code is not None:
            values["error_code"] = error_code
        if error_detail is not None:
            values["error_detail"] = error_detail
        if status in {"COMPLETED", "FAILED", "SKIPPED"}:
            values["completed_at"] = datetime.now(UTC)

        stmt = (
            update(ProcessingJobStep)
            .where(ProcessingJobStep.id == step_id)
            .values(**values)
        )
        await session.execute(stmt)

    async def get_completed_steps(
        self, job_id: uuid.UUID, session: AsyncSession
    ) -> list[ProcessingJobStep]:
        """Get all completed steps for a job."""
        stmt = select(ProcessingJobStep).where(
            ProcessingJobStep.job_id == job_id,
            ProcessingJobStep.step_status == "COMPLETED",
            ProcessingJobStep.is_deleted.is_(False),
        ).order_by(ProcessingJobStep.created_at.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_last_completed_step(
        self, job_id: uuid.UUID, session: AsyncSession
    ) -> ProcessingJobStep | None:
        """Get the last completed step for a job."""
        stmt = select(ProcessingJobStep).where(
            ProcessingJobStep.job_id == job_id,
            ProcessingJobStep.step_status == "COMPLETED",
            ProcessingJobStep.is_deleted.is_(False),
        ).order_by(ProcessingJobStep.completed_at.desc()).limit(1)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_checkpoint(
        self, step_id: uuid.UUID, checkpoint_data: dict[str, Any], session: AsyncSession
    ) -> None:
        """Save checkpoint data for a step."""
        stmt = (
            update(ProcessingJobStep)
            .where(ProcessingJobStep.id == step_id)
            .values(checkpoint_data=checkpoint_data, updated_at=datetime.now(UTC))
        )
        await session.execute(stmt)
