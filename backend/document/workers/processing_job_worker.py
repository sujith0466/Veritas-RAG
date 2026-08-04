"""Processing Job Worker.

Handles background cron tasks for stale job recovery.
"""

from contextlib import asynccontextmanager

from celery import shared_task

from backend.cache.redis import get_redis
from backend.database.engine import get_session_factory
from backend.document.repositories.job_audit_repository import JobAuditRepository
from backend.document.repositories.job_repository import JobRepository
from backend.document.repositories.job_step_repository import JobStepRepository
from backend.document.services.processing_job_service import ProcessingJobService


@asynccontextmanager
async def _get_job_service():
    """Helper to inject ProcessingJobService."""
    redis_client = await get_redis()
    session_factory = get_session_factory()
    async with session_factory() as session:
        job_repo = JobRepository()
        step_repo = JobStepRepository()
        audit_repo = JobAuditRepository()
        yield ProcessingJobService(job_repo, step_repo, audit_repo, redis_client), session


@shared_task(
    name="jobs.requeue_stale_jobs",
    bind=True,
    ignore_result=True,
)
def requeue_stale_jobs(self):
    """Cron task to recover jobs stuck in CLAIMED state."""
    import asyncio

    async def run():
        async with _get_job_service() as (service, session):
            # Find jobs claimed more than 5 minutes ago and requeue them
            count = await service.requeue_stale_jobs(threshold_minutes=5, session=session)
            if count > 0:
                print(f"Requeued {count} stale jobs")

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
