"""Celery Reliability Worker Tasks (`ADR-005`, `Phase 2 Milestone 5`).

Runs asynchronous SLA aggregations and circuit breaker decay sweeps.
"""

import asyncio
from typing import Any

import structlog

from backend.database.engine import get_session_factory
from backend.modules.reliability.circuit_breaker.engine import \
    CircuitBreakerEngine
from backend.modules.reliability.repositories.reliability_repository import \
    ReliabilityRepository
from backend.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, queue="retrieval", max_retries=2, acks_late=True)
def aggregate_sla_metrics_task(self: Any, tenant_id: str) -> dict[str, Any]:
    """Background Celery task computing aggregate SLA summaries for a tenant namespace."""
    return asyncio.run(_async_aggregate_sla_metrics(tenant_id))


async def _async_aggregate_sla_metrics(tenant_id: str) -> dict[str, Any]:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from backend.core.config import get_settings
    
    settings = get_settings().database
    engine = create_async_engine(settings.url, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    
    try:
        async with session_factory() as session:
            repo = ReliabilityRepository(session)
            summary = await repo.get_tenant_sla_summary(tenant_id)
            logger.info(
                "Aggregated SLA metrics background task completed",
                tenant_id=tenant_id,
                compliance_rate=summary.sla_compliance_rate,
                p95_ms=summary.p95_latency_ms,
            )
            return summary.model_dump()
    finally:
        await engine.dispose()


@celery_app.task(bind=True, queue="retrieval", max_retries=1, acks_late=True)
def check_and_decay_circuit_breakers_task(
    self: Any, tenant_id: str, target_module: str = "qdrant_hybrid"
) -> dict[str, Any]:
    """Background sweep checking state decay and triggering HALF_OPEN transitions."""
    return asyncio.run(_async_check_decay(tenant_id, target_module))


async def _async_check_decay(tenant_id: str, target_module: str) -> dict[str, Any]:
    engine = CircuitBreakerEngine()
    state = await engine.check_state(tenant_id=tenant_id, target=target_module)
    logger.debug(
        "Checked circuit breaker decay status",
        tenant_id=tenant_id,
        target=target_module,
        state=state.value,
    )
    return {
        "tenant_id": tenant_id,
        "target_module": target_module,
        "state": state.value,
    }
