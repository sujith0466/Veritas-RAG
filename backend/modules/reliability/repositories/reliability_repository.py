"""Reliability Repository (`ADR-005`, `Phase 2 Milestone 5`).

Provides asynchronous database operations for logging SLA compliance metrics,
circuit breaker state transitions, and aggregating tenant reliability summaries.
"""

import math
from collections.abc import Sequence
from typing import Optional
from uuid import UUID
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog
from backend.modules.reliability.models.circuit_event import CircuitBreakerEventLog
from backend.modules.reliability.models.sla_log import RetrievalSLALog
from backend.modules.reliability.schemas.reliability_dto import SLASummaryDTO
from backend.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class ReliabilityRepository(BaseRepository[RetrievalSLALog]):
    """Repository managing retrieval SLA compliance logs and circuit events (`ADR-005`)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_class=RetrievalSLALog)

    async def log_sla_metric(self, log_entity: RetrievalSLALog) -> UUID:
        """Insert a new SLA compliance log record into PostgreSQL (`retrieval_sla_logs`)."""
        self.session.add(log_entity)
        await self.session.commit()
        await self.session.refresh(log_entity)
        logger.debug(
            "Logged retrieval SLA metric",
            log_id=log_entity.id,
            tenant_id=log_entity.tenant_id,
            duration_ms=log_entity.duration_ms,
            breached=log_entity.is_sla_breached,
        )
        return log_entity.id

    async def log_circuit_event(self, event_entity: CircuitBreakerEventLog) -> UUID:
        """Insert a new circuit breaker event record into PostgreSQL (`circuit_breaker_events`)."""
        self.session.add(event_entity)
        await self.session.commit()
        await self.session.refresh(event_entity)
        logger.info(
            "Logged circuit breaker event",
            event_id=event_entity.id,
            tenant_id=event_entity.tenant_id,
            target=event_entity.target_module,
            transition=f"{event_entity.previous_state} -> {event_entity.new_state}",
        )
        return event_entity.id

    async def get_tenant_sla_summary(self, tenant_id: str) -> SLASummaryDTO:
        """Calculate aggregate SLA compliance rate, fallback frequencies, and P95 latency."""
        total_queries = (
            await self.session.scalar(
                select(func.count())
                .select_from(RetrievalSLALog)
                .where(RetrievalSLALog.tenant_id == tenant_id, RetrievalSLALog.is_deleted.is_(False))
            )
            or 0
        )

        breached_queries = (
            await self.session.scalar(
                select(func.count())
                .select_from(RetrievalSLALog)
                .where(
                    RetrievalSLALog.tenant_id == tenant_id,
                    RetrievalSLALog.is_sla_breached.is_(True),
                    RetrievalSLALog.is_deleted.is_(False),
                )
            )
            or 0
        )

        degraded_queries = (
            await self.session.scalar(
                select(func.count())
                .select_from(RetrievalSLALog)
                .where(
                    RetrievalSLALog.tenant_id == tenant_id,
                    RetrievalSLALog.is_degraded_fallback.is_(True),
                    RetrievalSLALog.is_deleted.is_(False),
                )
            )
            or 0
        )

        sla_compliance_rate = round(((total_queries - breached_queries) / total_queries) * 100, 2) if total_queries > 0 else 100.0

        p95_latency_ms = 0.0
        if total_queries > 0:
            durations_result = await self.session.scalars(
                select(RetrievalSLALog.duration_ms)
                .where(RetrievalSLALog.tenant_id == tenant_id, RetrievalSLALog.is_deleted.is_(False))
                .order_by(RetrievalSLALog.duration_ms.asc())
            )
            durations = list(durations_result.all())
            if durations:
                idx = max(0, math.ceil(len(durations) * 0.95) - 1)
                p95_latency_ms = round(float(durations[idx]), 2)

        return SLASummaryDTO(
            tenant_id=tenant_id,
            total_queries=total_queries,
            breached_queries=breached_queries,
            degraded_queries=degraded_queries,
            sla_compliance_rate=sla_compliance_rate,
            p95_latency_ms=p95_latency_ms,
        )

    async def get_recent_sla_logs(
        self, tenant_id: str, limit: int = 50, offset: int = 0
    ) -> Sequence[RetrievalSLALog]:
        """Fetch paginated SLA compliance logs for a tenant ordered by newest first."""
        result = await self.session.scalars(
            select(RetrievalSLALog)
            .where(RetrievalSLALog.tenant_id == tenant_id, RetrievalSLALog.is_deleted.is_(False))
            .order_by(desc(RetrievalSLALog.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.all()

    async def get_recent_circuit_events(
        self, tenant_id: str, target_module: Optional[str] = None, limit: int = 50
    ) -> Sequence[CircuitBreakerEventLog]:
        """Fetch recent circuit breaker transitions for a tenant."""
        query = (
            select(CircuitBreakerEventLog)
            .where(CircuitBreakerEventLog.tenant_id == tenant_id, CircuitBreakerEventLog.is_deleted.is_(False))
            .order_by(desc(CircuitBreakerEventLog.created_at))
            .limit(limit)
        )
        if target_module:
            query = query.where(CircuitBreakerEventLog.target_module == target_module)

        result = await self.session.scalars(query)
        return result.all()
