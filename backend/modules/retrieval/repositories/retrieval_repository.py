"""Retrieval Repository Implementation (`RetrievalRepository`).

Provides asynchronous database operations for tracking query audit logs,
percentile latency calculations ($P_{95}$), and stage timing aggregations (`ADR-005`).
"""

import math
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from backend.modules.retrieval.models.retrieval_log import RetrievalQueryLog
from backend.modules.retrieval.schemas.retrieval_dto import (
    RetrievalMetricsDTO, RetrievalQueryLogDTO, RetrievalStageBreakdownDTO)
from backend.repositories.base import BaseRepository

logger = get_logger(__name__)


class RetrievalRepository(BaseRepository[RetrievalQueryLog]):
    """Repository managing retrieval audit logs and tenant search KPIs (`ADR-005`)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_class=RetrievalQueryLog)

    async def log_query_execution(self, log_dto: RetrievalQueryLogDTO) -> UUID:
        """Insert a new query audit log record into PostgreSQL (`retrieval_queries`)."""
        log_entry = RetrievalQueryLog(
            id=log_dto.id,
            tenant_id=log_dto.tenant_id,
            correlation_id=log_dto.correlation_id,
            query_text=log_dto.query_text,
            dense_candidate_count=log_dto.dense_candidate_count,
            sparse_candidate_count=log_dto.sparse_candidate_count,
            merged_unique_count=log_dto.merged_unique_count,
            final_top_k=log_dto.final_top_k,
            total_duration_ms=log_dto.total_duration_ms,
            stage_breakdown_json=log_dto.stage_breakdown_json,
        )
        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        logger.debug(
            "Logged retrieval query execution",
            log_id=log_entry.id,
            tenant_id=log_dto.tenant_id,
            duration_ms=log_dto.total_duration_ms,
        )
        return log_entry.id

    async def get_query_history(
        self, tenant_id: str, limit: int = 50, offset: int = 0
    ) -> Sequence[RetrievalQueryLog]:
        """Fetch paginated retrieval history for a tenant namespace ordered by recent execution."""
        stmt = (
            select(RetrievalQueryLog)
            .where(
                RetrievalQueryLog.tenant_id == tenant_id,
                RetrievalQueryLog.is_deleted.is_(False),
            )
            .order_by(desc(RetrievalQueryLog.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_tenant_metrics(self, tenant_id: str) -> RetrievalMetricsDTO:
        """Compute aggregate KPIs ($P_{95}$ latency, avg candidates) for a tenant across history."""
        count_stmt = select(func.count(RetrievalQueryLog.id)).where(
            RetrievalQueryLog.tenant_id == tenant_id,
            RetrievalQueryLog.is_deleted.is_(False),
        )
        total_queries = (await self.session.execute(count_stmt)).scalar() or 0

        if total_queries == 0:
            return RetrievalMetricsDTO(tenant_id=tenant_id)

        avg_stmt = select(
            func.avg(RetrievalQueryLog.total_duration_ms),
            func.avg(RetrievalQueryLog.dense_candidate_count),
            func.avg(RetrievalQueryLog.sparse_candidate_count),
            func.avg(RetrievalQueryLog.merged_unique_count),
        ).where(
            RetrievalQueryLog.tenant_id == tenant_id,
            RetrievalQueryLog.is_deleted.is_(False),
        )
        avg_res = (await self.session.execute(avg_stmt)).first()
        avg_duration = float(avg_res[0] or 0.0) if avg_res else 0.0
        avg_dense = float(avg_res[1] or 0.0) if avg_res else 0.0
        avg_sparse = float(avg_res[2] or 0.0) if avg_res else 0.0
        avg_merged = float(avg_res[3] or 0.0) if avg_res else 0.0

        # Fetch durations ordered ascending to compute exact P95 index
        durations_stmt = (
            select(RetrievalQueryLog.total_duration_ms)
            .where(
                RetrievalQueryLog.tenant_id == tenant_id,
                RetrievalQueryLog.is_deleted.is_(False),
            )
            .order_by(RetrievalQueryLog.total_duration_ms.asc())
        )
        durations = (await self.session.execute(durations_stmt)).scalars().all()
        p95_idx = max(0, math.ceil(len(durations) * 0.95) - 1)
        p95_duration = float(durations[p95_idx]) if durations else 0.0

        # Average stage latencies from recent 100 queries
        recent_stmt = (
            select(RetrievalQueryLog.stage_breakdown_json)
            .where(
                RetrievalQueryLog.tenant_id == tenant_id,
                RetrievalQueryLog.is_deleted.is_(False),
            )
            .order_by(desc(RetrievalQueryLog.created_at))
            .limit(100)
        )
        recent_breakdowns = (await self.session.execute(recent_stmt)).scalars().all()

        dense_ms_sum = 0.0
        sparse_ms_sum = 0.0
        rrf_ms_sum = 0.0
        rerank_ms_sum = 0.0
        count_b = len(recent_breakdowns)
        for b in recent_breakdowns:
            if isinstance(b, dict):
                dense_ms_sum += float(b.get("dense_ms", 0.0))
                sparse_ms_sum += float(b.get("sparse_ms", 0.0))
                rrf_ms_sum += float(b.get("rrf_fusion_ms", 0.0))
                rerank_ms_sum += float(b.get("rerank_ms", 0.0))

        stage_avg = RetrievalStageBreakdownDTO(
            dense_ms=round(dense_ms_sum / count_b, 2) if count_b > 0 else 0.0,
            sparse_ms=round(sparse_ms_sum / count_b, 2) if count_b > 0 else 0.0,
            rrf_fusion_ms=round(rrf_ms_sum / count_b, 2) if count_b > 0 else 0.0,
            rerank_ms=round(rerank_ms_sum / count_b, 2) if count_b > 0 else 0.0,
            total_ms=round(avg_duration, 2),
        )

        return RetrievalMetricsDTO(
            tenant_id=tenant_id,
            total_queries_executed=total_queries,
            avg_total_duration_ms=round(avg_duration, 2),
            p95_total_duration_ms=round(p95_duration, 2),
            avg_dense_candidates=round(avg_dense, 2),
            avg_sparse_candidates=round(avg_sparse, 2),
            avg_merged_candidates=round(avg_merged, 2),
            stage_latencies_avg=stage_avg,
        )
