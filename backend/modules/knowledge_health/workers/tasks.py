"""Celery Worker Tasks for Knowledge Health (`ADR-005`, `Phase 2 Milestone 6`).

Runs background orphan sweeps, parity audits, and two-phase hard purges.
"""

import asyncio
from typing import Any
from uuid import UUID

import structlog

from backend.modules.knowledge_health.schemas.health_dto import ScanType
from backend.modules.knowledge_health.services.health_service import KnowledgeHealthOrchestrator
from backend.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, queue="ingestion", max_retries=2, acks_late=True)
def run_scheduled_orphan_sweep_task(self: Any, tenant_id: str) -> dict[str, Any]:
    """Background Celery task executing orphan chunk and vector cleanup sweeps (`ADR-M6-001`)."""
    return asyncio.run(_async_run_orphan_sweep(tenant_id))


async def _async_run_orphan_sweep(tenant_id: str) -> dict[str, Any]:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from backend.core.config import get_settings

    settings = get_settings().database
    engine = create_async_engine(settings.url, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

    try:
        async with session_factory() as session:
            service = KnowledgeHealthOrchestrator(session)
            job_dto = await service.run_health_scan(
                tenant_id=tenant_id, scan_type=ScanType.ORPHAN_SWEEP
            )
            logger.info(
                "Completed scheduled orphan sweep task",
                tenant_id=tenant_id,
                purged=job_dto.orphans_purged,
            )
            return job_dto.model_dump()
    finally:
        await engine.dispose()


@celery_app.task(bind=True, queue="ingestion", max_retries=2, acks_late=True)
def run_scheduled_parity_audit_task(self: Any, tenant_id: str) -> dict[str, Any]:
    """Background Celery task auditing 1:1 count parity across PostgreSQL and Qdrant (`ADR-M6-001`)."""
    return asyncio.run(_async_run_parity_audit(tenant_id))


async def _async_run_parity_audit(tenant_id: str) -> dict[str, Any]:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from backend.core.config import get_settings

    settings = get_settings().database
    engine = create_async_engine(settings.url, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

    try:
        async with session_factory() as session:
            service = KnowledgeHealthOrchestrator(session)
            job_dto = await service.run_health_scan(
                tenant_id=tenant_id, scan_type=ScanType.PARITY_AUDIT
            )
            logger.info(
                "Completed scheduled parity audit task",
                tenant_id=tenant_id,
                parity=job_dto.parity_status,
            )
            return job_dto.model_dump()
    finally:
        await engine.dispose()


@celery_app.task(bind=True, queue="ingestion", max_retries=3, acks_late=True)
def execute_hard_purge_task(
    self: Any, document_id: str, tenant_id: str
) -> dict[str, Any]:
    """Background Celery task executing Phase 2 hard purge of vectors and DB rows (`ADR-M6-001`)."""
    return asyncio.run(_async_execute_hard_purge(document_id, tenant_id))


async def _async_execute_hard_purge(document_id: str, tenant_id: str) -> dict[str, Any]:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from backend.core.config import get_settings

    settings = get_settings().database
    engine = create_async_engine(settings.url, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

    try:
        async with session_factory() as session:
            service = KnowledgeHealthOrchestrator(session)
            doc_uuid = UUID(str(document_id))
            summary = await service.execute_two_phase_purge(doc_uuid, tenant_id=tenant_id)
            logger.info(
                "Completed background Phase 2 hard purge task",
                document_id=document_id,
                vectors=summary.qdrant_points_deleted,
            )
            return summary.model_dump()
    finally:
        await engine.dispose()
