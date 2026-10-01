"""Execution Intelligence & Forensics Service (`DASH-003`).

Provides paginated execution ledgers and deep forensic trace inspection
for authorized administrators while strictly enforcing tenant boundaries.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.modules.analytics.models.query_analytics import QueryAnalyticsRecord
from backend.modules.dashboard.schemas.dashboard_dto import (
    QueryExecutionLedgerDTO,
    QueryExecutionLedgerItemDTO,
    QueryExecutionTraceDTO,
    RetrievalTraceDetailDTO,
)
from backend.modules.retrieval.models.retrieval_log import RetrievalQueryLog

logger = structlog.get_logger(__name__)


class ExecutionIntelligenceService:
    """Service for querying execution ledgers and detailed forensics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_executions(
        self,
        tenant_id: str,
        time_window: str = "24h",
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
        min_reliability: float | None = None,
    ) -> QueryExecutionLedgerDTO:
        """Fetch a paginated ledger of query executions scoped to tenant_id."""
        now_utc = datetime.now(UTC)
        cutoff: datetime | None = None
        if time_window == "1h":
            cutoff = now_utc - timedelta(hours=1)
        elif time_window == "24h":
            cutoff = now_utc - timedelta(hours=24)
        elif time_window == "7d":
            cutoff = now_utc - timedelta(days=7)
        elif time_window == "30d":
            cutoff = now_utc - timedelta(days=30)
        elif time_window == "all":
            cutoff = None
        else:
            cutoff = now_utc - timedelta(hours=24)
            time_window = "24h"

        # Base query filtered by tenant_id
        base_filter = [QueryAnalyticsRecord.tenant_id == tenant_id]

        if cutoff is not None:
            base_filter.append(QueryAnalyticsRecord.created_at >= cutoff)

        if status and status.upper() != "ALL":
            base_filter.append(QueryAnalyticsRecord.outcome == status.upper())

        if search:
            base_filter.append(QueryAnalyticsRecord.query_text.ilike(f"%{search}%"))

        if min_reliability is not None:
            base_filter.append(QueryAnalyticsRecord.reliability_score >= min_reliability)

        # Count total matching rows
        count_query = select(func.count(QueryAnalyticsRecord.id)).where(*base_filter)
        total_res = await self._session.execute(count_query)
        total_count = total_res.scalar() or 0

        # Fetch page items
        query = (
            select(QueryAnalyticsRecord)
            .where(*base_filter)
            .order_by(QueryAnalyticsRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items_res = await self._session.execute(query)
        records = items_res.scalars().all()

        # Check retrieval logs presence for these records in batch
        corr_ids = [r.correlation_id for r in records if r.correlation_id]
        existing_retrievals = set()
        if corr_ids:
            ret_check = await self._session.execute(
                select(RetrievalQueryLog.correlation_id).where(
                    RetrievalQueryLog.tenant_id == tenant_id,
                    RetrievalQueryLog.correlation_id.in_(corr_ids),
                )
            )
            existing_retrievals = set(ret_check.scalars().all())

        items: list[QueryExecutionLedgerItemDTO] = []
        for r in records:
            dt_str = r.created_at.isoformat() if r.created_at else now_utc.isoformat()
            items.append(
                QueryExecutionLedgerItemDTO(
                    id=str(r.id),
                    correlation_id=r.correlation_id,
                    query_text=r.query_text,
                    outcome=r.outcome,
                    confidence_score=r.confidence_score,
                    reliability_score=r.reliability_score,
                    hallucination_score=r.hallucination_score,
                    retry_attempts=r.retry_attempts,
                    duration_ms=round(r.total_duration_ms, 2),
                    is_safe_to_serve=r.is_safe_to_serve,
                    timestamp=dt_str,
                    has_retrieval_trace=r.correlation_id in existing_retrievals,
                )
            )

        return QueryExecutionLedgerDTO(
            items=items,
            total=total_count,
            limit=limit,
            offset=offset,
            time_window=time_window,
        )

    async def get_execution_trace(
        self, tenant_id: str, query_id: str
    ) -> QueryExecutionTraceDTO | None:
        """Fetch full forensic trace for an execution, ensuring strict tenant isolation."""
        try:
            parsed_uuid = uuid.UUID(query_id)
        except ValueError:
            return None

        # 1. Fetch QueryAnalyticsRecord scoped strictly by tenant_id
        q_record = await self._session.execute(
            select(QueryAnalyticsRecord).where(
                QueryAnalyticsRecord.id == parsed_uuid,
                QueryAnalyticsRecord.tenant_id == tenant_id,
            )
        )
        record = q_record.scalar_one_or_none()
        if not record:
            return None

        # 2. Fetch associated RetrievalQueryLog
        retrieval_dto: RetrievalTraceDetailDTO | None = None
        diagnostics: dict[str, str] = {}

        if record.correlation_id:
            ret_res = await self._session.execute(
                select(RetrievalQueryLog).where(
                    RetrievalQueryLog.tenant_id == tenant_id,
                    RetrievalQueryLog.correlation_id == record.correlation_id,
                )
            )
            ret_log = ret_res.scalar_one_or_none()
            if ret_log:
                retrieval_dto = RetrievalTraceDetailDTO(
                    dense_candidate_count=ret_log.dense_candidate_count,
                    sparse_candidate_count=ret_log.sparse_candidate_count,
                    merged_unique_count=ret_log.merged_unique_count,
                    final_top_k=ret_log.final_top_k,
                    retrieval_duration_ms=round(ret_log.total_duration_ms, 2),
                    stage_breakdown=ret_log.stage_breakdown_json or {},
                )
                diagnostics["retrieval_status"] = "RETRIEVAL_LOG_LINKED"
            else:
                diagnostics["retrieval_status"] = "RETRIEVAL_LOG_NOT_FOUND"
        else:
            diagnostics["retrieval_status"] = "NO_CORRELATION_ID"

        diagnostics["pipeline_type"] = "SELF_CORRECTING_HYBRID_RAG"
        diagnostics["verified_safe"] = str(record.is_safe_to_serve)

        dt_str = record.created_at.isoformat() if record.created_at else datetime.now(UTC).isoformat()

        return QueryExecutionTraceDTO(
            id=str(record.id),
            correlation_id=record.correlation_id,
            tenant_id=record.tenant_id,
            query_text=record.query_text,
            outcome=record.outcome,
            confidence_score=record.confidence_score,
            reliability_score=record.reliability_score,
            hallucination_score=record.hallucination_score,
            retry_attempts=record.retry_attempts,
            total_duration_ms=round(record.total_duration_ms, 2),
            is_safe_to_serve=record.is_safe_to_serve,
            timestamp=dt_str,
            retrieval=retrieval_dto,
            diagnostics=diagnostics,
        )
