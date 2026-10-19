"""Retrieval Repository Implementation (`RetrievalRepository`).

Provides asynchronous database operations for tracking query audit logs,
percentile latency calculations ($P_{95}$), and stage timing aggregations (`ADR-005`).
"""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
import math
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from backend.modules.retrieval.models.retrieval_log import RetrievalQueryLog
from backend.modules.retrieval.schemas.retrieval_dto import (
    RetrievalMetricsDTO,
    RetrievalQueryLogDTO,
    RetrievalStageBreakdownDTO,
)
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

    async def filter_active_ready_document_ids(
        self, document_ids: set[UUID], tenant_id: str
    ) -> set[UUID]:
        """Filter candidate document IDs, ensuring they are active (not deleted) and in READY status for tenant."""
        if not document_ids:
            return set()
        from backend.document.models.document import Document
        from backend.document.models.status import DocumentStatus

        stmt = (
            select(Document.id)
            .where(
                Document.id.in_(document_ids),
                Document.tenant_id == str(tenant_id),
                Document.is_deleted.is_(False),
                Document.status == DocumentStatus.READY.value,
            )
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def validate_active_candidates(
        self,
        candidate_tuples: set[tuple[UUID, UUID, UUID]],
        tenant_id: str,
    ) -> set[tuple[UUID, UUID, UUID]]:
        """Validate candidate (chunk_id, document_id, version_id) tuples against authoritative PostgreSQL state.

        Asserts:
        1. DocumentChunk belongs to Document and DocumentVersion for this tenant.
        2. Document is not deleted and status == READY.
        3. DocumentVersion is not deleted and is_active_vector is True.
        4. Document.latest_version_id == DocumentVersion.id (version is current).
        """
        if not candidate_tuples:
            return set()

        from backend.document.models.document import Document, DocumentVersion
        from backend.document.models.status import DocumentStatus
        from backend.modules.chunking.models.chunk import DocumentChunk

        chunk_ids = {t[0] for t in candidate_tuples}
        stmt = (
            select(
                DocumentChunk.id,
                Document.id,
                DocumentVersion.id,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .join(DocumentVersion, DocumentChunk.document_version_id == DocumentVersion.id)
            .where(
                DocumentChunk.id.in_(chunk_ids),
                Document.tenant_id == str(tenant_id),
                Document.is_deleted.is_(False),
                Document.status == DocumentStatus.READY.value,
                DocumentVersion.is_deleted.is_(False),
                DocumentVersion.is_active_vector.is_(True),
                Document.latest_version_id == DocumentVersion.id,
            )
        )
        result = await self.session.execute(stmt)
        valid_tuples = {(row[0], row[1], row[2]) for row in result.all()}
        return valid_tuples

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
        """Calculate aggregated search performance KPIs over the last 30 days (`AUD-013`).

        Computes continuous P95 percentile latency, average durations, and stage breakdowns.
        Uses PostgreSQL native percentile_cont(0.95) in production, and continuous rank
        interpolation in SQLite test harnesses.
        """
        dialect_name = "postgresql"
        try:
            bind = getattr(self.session, "bind", None) or self.session.get_bind()
            if bind and hasattr(bind, "dialect") and bind.dialect.name:
                dialect_name = bind.dialect.name
        except Exception:
            dialect_name = "postgresql"

        # SQLite strips tzinfo on read-back, requiring naive UTC cutoff; PostgreSQL requires aware UTC
        if dialect_name == "sqlite":
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).replace(tzinfo=None)
        else:
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        count_stmt = select(func.count(RetrievalQueryLog.id)).where(
            RetrievalQueryLog.tenant_id == tenant_id,
            RetrievalQueryLog.is_deleted.is_(False),
            RetrievalQueryLog.created_at >= cutoff,
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
            RetrievalQueryLog.created_at >= cutoff,
        )
        avg_res = (await self.session.execute(avg_stmt)).first()
        avg_duration = float(avg_res[0] or 0.0) if avg_res else 0.0
        avg_dense = float(avg_res[1] or 0.0) if avg_res else 0.0
        avg_sparse = float(avg_res[2] or 0.0) if avg_res else 0.0
        avg_merged = float(avg_res[3] or 0.0) if avg_res else 0.0

        if dialect_name == "postgresql":
            # PostgreSQL native continuous percentile within 30-day window
            p95_stmt = select(
                func.percentile_cont(0.95).within_group(RetrievalQueryLog.total_duration_ms.asc())
            ).where(
                RetrievalQueryLog.tenant_id == tenant_id,
                RetrievalQueryLog.is_deleted.is_(False),
                RetrievalQueryLog.created_at >= cutoff,
            )
            p95_val = (await self.session.execute(p95_stmt)).scalar_one_or_none()
            p95_duration = float(p95_val or 0.0)
        else:
            # SQLite / Test Harness: continuous linear interpolation matching percentile_cont(0.95)
            durations_stmt = (
                select(RetrievalQueryLog.total_duration_ms)
                .where(
                    RetrievalQueryLog.tenant_id == tenant_id,
                    RetrievalQueryLog.is_deleted.is_(False),
                    RetrievalQueryLog.created_at >= cutoff,
                )
                .order_by(RetrievalQueryLog.total_duration_ms.asc())
            )
            durations = [float(d) for d in (await self.session.execute(durations_stmt)).scalars().all()]
            n = len(durations)
            if n == 0:
                p95_duration = 0.0
            elif n == 1:
                p95_duration = durations[0]
            else:
                # Continuous rank matching PostgreSQL percentile_cont(0.95):
                # Rank R = 1 + 0.95 * (n - 1) (1-indexed) -> (R - 1) in 0-indexed terms: 0.95 * (n - 1)
                rank = 0.95 * (n - 1)
                lower_idx = int(math.floor(rank))
                upper_idx = int(math.ceil(rank))
                fraction = rank - lower_idx
                p95_duration = durations[lower_idx] + fraction * (durations[upper_idx] - durations[lower_idx])

        # Average stage latencies from recent 100 queries within 30-day window
        recent_stmt = (
            select(RetrievalQueryLog.stage_breakdown_json)
            .where(
                RetrievalQueryLog.tenant_id == tenant_id,
                RetrievalQueryLog.is_deleted.is_(False),
                RetrievalQueryLog.created_at >= cutoff,
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
            p95_total_duration_ms=round(p95_duration, 4),
            avg_dense_candidates=round(avg_dense, 2),
            avg_sparse_candidates=round(avg_sparse, 2),
            avg_merged_candidates=round(avg_merged, 2),
            stage_latencies_avg=stage_avg,
        )
