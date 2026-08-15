"""Analytics Repository (`ADR-005`, `Phase 4 Milestone 1`).

Provides asynchronous database operations for logging query analytics records
and computing aggregations across query outcomes, confidence, latency, and reliability.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
import math
from typing import Any
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.modules.analytics.models.query_analytics import QueryAnalyticsRecord
from backend.modules.analytics.schemas.analytics_dto import (
    ConfidenceAnalyticsDTO,
    LatencyAnalyticsDTO,
    QueryTrendsDTO,
    ReliabilityHistoryDTO,
    SearchAnalyticsDTO,
    SuccessRateDTO,
    WorkspaceOverviewDTO,
)
from backend.modules.retrieval.models.retrieval_log import RetrievalQueryLog
from backend.document.models.document import Document
from backend.document.models.status import DocumentStatus
from backend.modules.chat.models.chat_session import ChatSession
from backend.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class AnalyticsRepository(BaseRepository[QueryAnalyticsRecord]):
    """Repository managing query execution analytics records and computing enterprise KPIs."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_class=QueryAnalyticsRecord)

    async def log_query_execution(self, record: QueryAnalyticsRecord) -> UUID:
        """Insert a new query analytics execution record into PostgreSQL (`query_analytics_records`)."""
        if record.id is None:
            import uuid

            record.id = uuid.uuid4()
        if record.created_at is None:
            record.created_at = datetime.now(UTC)
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        logger.debug(
            "Logged query analytics record",
            record_id=record.id,
            tenant_id=record.tenant_id,
            outcome=record.outcome,
            reliability=record.reliability_score,
        )
        return record.id

    async def get_workspace_overview(
        self,
        tenant_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> WorkspaceOverviewDTO:
        """Calculate high-level snapshot metrics for the workspace."""

        # 1. Active Users (distinct user_ids from ChatSession)
        user_query = select(func.count(func.distinct(ChatSession.user_id))).where(
            ChatSession.tenant_id == tenant_id,
        )
        if start_time:
            user_query = user_query.where(ChatSession.created_at >= start_time)
        if end_time:
            user_query = user_query.where(ChatSession.created_at <= end_time)
        active_users = (await self.session.scalar(user_query)) or 0

        # 2. Document Count (active documents)
        doc_query = select(func.count(Document.id)).where(
            Document.tenant_id == tenant_id,
            Document.status == DocumentStatus.READY,
        )
        document_count = (await self.session.scalar(doc_query)) or 0

        # 3. Total Queries
        queries_query = select(func.count(QueryAnalyticsRecord.id)).where(
            QueryAnalyticsRecord.tenant_id == tenant_id,
            QueryAnalyticsRecord.is_deleted.is_(False),
        )
        if start_time:
            queries_query = queries_query.where(QueryAnalyticsRecord.created_at >= start_time)
        if end_time:
            queries_query = queries_query.where(QueryAnalyticsRecord.created_at <= end_time)
        total_queries = (await self.session.scalar(queries_query)) or 0

        return WorkspaceOverviewDTO(
            active_users=active_users,
            document_count=document_count,
            total_queries=total_queries,
        )

    async def list_query_history(
        self,
        tenant_id: str,
        limit: int = 50,
        offset: int = 0,
        outcome_filter: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> tuple[Sequence[QueryAnalyticsRecord], int]:
        """Fetch paginated query execution records matching filters."""
        query = select(QueryAnalyticsRecord).where(
            QueryAnalyticsRecord.tenant_id == tenant_id,
            QueryAnalyticsRecord.is_deleted.is_(False),
        )
        count_query = (
            select(func.count())
            .select_from(QueryAnalyticsRecord)
            .where(
                QueryAnalyticsRecord.tenant_id == tenant_id,
                QueryAnalyticsRecord.is_deleted.is_(False),
            )
        )

        if outcome_filter:
            query = query.where(QueryAnalyticsRecord.outcome == outcome_filter)
            count_query = count_query.where(
                QueryAnalyticsRecord.outcome == outcome_filter
            )
        if start_time:
            query = query.where(QueryAnalyticsRecord.created_at >= start_time)
            count_query = count_query.where(
                QueryAnalyticsRecord.created_at >= start_time
            )
        if end_time:
            query = query.where(QueryAnalyticsRecord.created_at <= end_time)
            count_query = count_query.where(QueryAnalyticsRecord.created_at <= end_time)

        total = (await self.session.scalar(count_query)) or 0
        result = await self.session.scalars(
            query.order_by(desc(QueryAnalyticsRecord.created_at))
            .limit(limit)
            .offset(offset)
        )
        return result.all(), total

    async def get_record_by_correlation_id(
        self, correlation_id: str, tenant_id: str
    ) -> QueryAnalyticsRecord | None:
        """Fetch a single query analytics record by its correlation trace ID."""
        query = select(QueryAnalyticsRecord).where(
            QueryAnalyticsRecord.correlation_id == correlation_id,
            QueryAnalyticsRecord.tenant_id == tenant_id,
            QueryAnalyticsRecord.is_deleted.is_(False),
        )
        return await self.session.scalar(query)

    async def get_success_rate_metrics(
        self,
        tenant_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> SuccessRateDTO:
        """Calculate overall success, clarification, and failure rates across queries."""
        query = select(QueryAnalyticsRecord).where(
            QueryAnalyticsRecord.tenant_id == tenant_id,
            QueryAnalyticsRecord.is_deleted.is_(False),
        )
        if start_time:
            query = query.where(QueryAnalyticsRecord.created_at >= start_time)
        if end_time:
            query = query.where(QueryAnalyticsRecord.created_at <= end_time)

        records = list((await self.session.scalars(query)).all())
        total = len(records)
        if total == 0:
            return SuccessRateDTO(
                total_queries=0,
                success_count=0,
                clarification_count=0,
                failure_count=0,
                retry_count=0,
                success_rate_percentage=100.0,
                avg_retries_per_query=0.0,
            )

        success_count = sum(1 for r in records if r.outcome == "SUCCESS")
        clarification_count = sum(
            1 for r in records if r.outcome == "CLARIFICATION_REQUIRED"
        )
        failure_count = sum(
            1
            for r in records
            if r.outcome
            in (
                "ABORTED_LOW_CONFIDENCE",
                "ABORTED_HALLUCINATION",
                "ABORTED_MAX_RETRIES",
            )
        )
        retry_count = sum(1 for r in records if r.retry_attempts > 0)
        total_retries = sum(r.retry_attempts for r in records)

        success_rate = round((success_count / total) * 100, 2)
        avg_retries = round(total_retries / total, 2)

        return SuccessRateDTO(
            total_queries=total,
            success_count=success_count,
            clarification_count=clarification_count,
            failure_count=failure_count,
            retry_count=retry_count,
            success_rate_percentage=success_rate,
            avg_retries_per_query=avg_retries,
        )

    async def get_latency_analytics(
        self,
        tenant_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> LatencyAnalyticsDTO:
        """Calculate P50, P90, P95, P99 and mean execution latencies across queries."""
        query = select(QueryAnalyticsRecord.total_duration_ms).where(
            QueryAnalyticsRecord.tenant_id == tenant_id,
            QueryAnalyticsRecord.is_deleted.is_(False),
        )
        if start_time:
            query = query.where(QueryAnalyticsRecord.created_at >= start_time)
        if end_time:
            query = query.where(QueryAnalyticsRecord.created_at <= end_time)

        durations = sorted(
            list(
                (
                    await self.session.scalars(
                        query.order_by(QueryAnalyticsRecord.total_duration_ms.asc())
                    )
                ).all()
            )
        )
        total = len(durations)
        if total == 0:
            return LatencyAnalyticsDTO(
                p50_ms=0.0, p90_ms=0.0, p95_ms=0.0, p99_ms=0.0, avg_ms=0.0
            )

        def get_percentile(pct: float) -> float:
            idx = max(0, math.ceil(total * pct) - 1)
            return round(float(durations[idx]), 2)

        avg_ms = round(sum(durations) / total, 2)
        return LatencyAnalyticsDTO(
            p50_ms=get_percentile(0.50),
            p90_ms=get_percentile(0.90),
            p95_ms=get_percentile(0.95),
            p99_ms=get_percentile(0.99),
            avg_ms=avg_ms,
        )

    async def get_confidence_analytics(
        self,
        tenant_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> ConfidenceAnalyticsDTO:
        """Calculate confidence distribution statistics."""
        query = select(QueryAnalyticsRecord.confidence_score).where(
            QueryAnalyticsRecord.tenant_id == tenant_id,
            QueryAnalyticsRecord.confidence_score.is_not(None),
            QueryAnalyticsRecord.is_deleted.is_(False),
        )
        if start_time:
            query = query.where(QueryAnalyticsRecord.created_at >= start_time)
        if end_time:
            query = query.where(QueryAnalyticsRecord.created_at <= end_time)

        scores = [
            float(s) for s in (await self.session.scalars(query)).all() if s is not None
        ]
        total = len(scores)
        if total == 0:
            return ConfidenceAnalyticsDTO(
                avg_confidence=0.0,
                min_confidence=0.0,
                max_confidence=0.0,
                high_confidence_count=0,
                medium_confidence_count=0,
                low_confidence_count=0,
            )

        high_cnt = sum(1 for s in scores if s >= 0.75)
        med_cnt = sum(1 for s in scores if 0.40 <= s < 0.75)
        low_cnt = sum(1 for s in scores if s < 0.40)

        return ConfidenceAnalyticsDTO(
            avg_confidence=round(sum(scores) / total, 4),
            min_confidence=round(min(scores), 4),
            max_confidence=round(max(scores), 4),
            high_confidence_count=high_cnt,
            medium_confidence_count=med_cnt,
            low_confidence_count=low_cnt,
        )

    async def get_query_trends(
        self,
        tenant_id: str,
        interval: str = "daily",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> QueryTrendsDTO:
        """Compute time-bucketed trends across query counts, confidence, and reliability."""
        query = select(QueryAnalyticsRecord).where(
            QueryAnalyticsRecord.tenant_id == tenant_id,
            QueryAnalyticsRecord.is_deleted.is_(False),
        )
        if start_time:
            query = query.where(QueryAnalyticsRecord.created_at >= start_time)
        if end_time:
            query = query.where(QueryAnalyticsRecord.created_at <= end_time)

        records = sorted(
            list((await self.session.scalars(query)).all()), key=lambda r: r.created_at
        )
        buckets: dict[str, list[QueryAnalyticsRecord]] = {}

        for r in records:
            dt = r.created_at
            if interval == "hourly":
                key = dt.strftime("%Y-%m-%dT%H:00:00Z")
            elif interval == "weekly":
                # Year and ISO week number
                key = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
            else:  # daily
                key = dt.strftime("%Y-%m-%d")
            buckets.setdefault(key, []).append(r)

        timestamps = list(buckets.keys())
        counts = []
        avg_conf = []
        avg_rel = []

        for key, recs in buckets.items():
            counts.append(len(recs))
            confs = [r.confidence_score for r in recs if r.confidence_score is not None]
            rels = [
                r.reliability_score for r in recs if r.reliability_score is not None
            ]
            avg_conf.append(round(sum(confs) / len(confs), 4) if confs else 0.0)
            avg_rel.append(round(sum(rels) / len(rels), 2) if rels else 0.0)

        return QueryTrendsDTO(
            timestamps=timestamps,
            query_counts=counts,
            avg_confidence_scores=avg_conf,
            avg_reliability_scores=avg_rel,
        )

    async def get_reliability_history(
        self,
        tenant_id: str,
        interval: str = "daily",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> ReliabilityHistoryDTO:
        """Compute reliability history timeline with moving averages."""
        trends = await self.get_query_trends(
            tenant_id=tenant_id,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
        )
        scores = trends.avg_reliability_scores
        moving_avg = []
        for i in range(len(scores)):
            window = scores[max(0, i - 2) : i + 1]
            moving_avg.append(round(sum(window) / len(window), 2))

        return ReliabilityHistoryDTO(
            timestamps=trends.timestamps,
            scores=scores,
            moving_average_scores=moving_avg,
        )

    async def get_popular_topics(
        self,
        tenant_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Extract the most frequent lexemes/topics from query_text."""
        lexeme = func.unnest(func.tsvector_to_array(func.to_tsvector('english', QueryAnalyticsRecord.query_text))).label('topic')
        query = select(
            lexeme,
            func.count().label('count')
        ).where(
            QueryAnalyticsRecord.tenant_id == tenant_id,
            QueryAnalyticsRecord.is_deleted.is_(False)
        )

        if start_time:
            query = query.where(QueryAnalyticsRecord.created_at >= start_time)
        if end_time:
            query = query.where(QueryAnalyticsRecord.created_at <= end_time)

        query = query.group_by(lexeme).order_by(desc('count')).limit(limit)

        result = await self.session.execute(query)
        return [{"topic": row.topic, "count": row.count} for row in result.all()]

    async def get_unanswered_queries(
        self,
        tenant_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List queries that failed to produce a final successful outcome."""
        unanswered_outcomes = [
            "CLARIFICATION_REQUIRED",
            "ABORTED_LOW_CONFIDENCE",
            "ABORTED_HALLUCINATION",
            "ABORTED_MAX_RETRIES",
        ]

        query = select(
            QueryAnalyticsRecord.query_text,
            QueryAnalyticsRecord.outcome,
            func.count().label('count'),
            func.max(QueryAnalyticsRecord.created_at).label('last_seen')
        ).where(
            QueryAnalyticsRecord.tenant_id == tenant_id,
            QueryAnalyticsRecord.outcome.in_(unanswered_outcomes),
            QueryAnalyticsRecord.is_deleted.is_(False)
        )

        if start_time:
            query = query.where(QueryAnalyticsRecord.created_at >= start_time)
        if end_time:
            query = query.where(QueryAnalyticsRecord.created_at <= end_time)

        query = query.group_by(
            QueryAnalyticsRecord.query_text,
            QueryAnalyticsRecord.outcome
        ).order_by(desc('count')).limit(limit)

        result = await self.session.execute(query)
        return [
            {
                "query_text": row.query_text,
                "outcome": row.outcome,
                "count": row.count,
                "last_seen": row.last_seen
            } for row in result.all()
        ]

    async def get_reliability_trends(
        self,
        tenant_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Compute the average reliability score per day."""
        date_bucket = func.date_trunc('day', QueryAnalyticsRecord.created_at).label('date')
        query = select(
            date_bucket,
            func.avg(QueryAnalyticsRecord.reliability_score).label('average_score')
        ).where(
            QueryAnalyticsRecord.tenant_id == tenant_id,
            QueryAnalyticsRecord.reliability_score.is_not(None),
            QueryAnalyticsRecord.is_deleted.is_(False)
        )

        if start_time:
            query = query.where(QueryAnalyticsRecord.created_at >= start_time)
        if end_time:
            query = query.where(QueryAnalyticsRecord.created_at <= end_time)

        query = query.group_by(date_bucket).order_by(date_bucket.asc())

        result = await self.session.execute(query)
        return [
            {
                "date": row.date.strftime("%Y-%m-%d") if row.date else "",
                "average_score": round(row.average_score, 2) if row.average_score is not None else 0.0
            } for row in result.all()
        ]

    async def get_most_cited_documents(
        self,
        tenant_id: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Aggregate citation counts from chat message JSONB."""
        from backend.modules.chat.models.chat_message import ChatMessage
        from backend.modules.chat.models.chat_session import ChatSession

        citation_elem = func.jsonb_array_elements(
            func.cast(ChatMessage.citations, func.jsonb())
        ).label('citation')

        query = select(
            citation_elem.op('->>')('document_id').label('document_id'),
            citation_elem.op('->>')('document_name').label('document_name'),
            func.count().label('citation_count'),
            func.max(ChatMessage.created_at).label('last_cited_at')
        ).select_from(
            ChatMessage
        ).join(
            ChatSession, ChatMessage.session_id == ChatSession.id
        ).where(
            ChatSession.tenant_id == tenant_id,
            ChatMessage.citations.is_not(None)
        )

        if start_time:
            query = query.where(ChatMessage.created_at >= start_time)
        if end_time:
            query = query.where(ChatMessage.created_at <= end_time)

        query = query.group_by(
            citation_elem.op('->>')('document_id'),
            citation_elem.op('->>')('document_name')
        ).order_by(
            desc('citation_count')
        ).limit(limit)

        result = await self.session.execute(query)
        return [
            {
                "document_id": row.document_id,
                "document_title": row.document_name or "Unknown Document",
                "citation_count": row.citation_count,
                "last_cited_at": row.last_cited_at
            } for row in result.all() if row.document_id
        ]

    async def get_search_analytics(self, tenant_id: str) -> SearchAnalyticsDTO:
        """Aggregate retrieval stage performance across `RetrievalQueryLog` table."""
        query = select(RetrievalQueryLog).where(
            RetrievalQueryLog.tenant_id == tenant_id,
            RetrievalQueryLog.is_deleted.is_(False),
        )
        logs = list((await self.session.scalars(query)).all())
        total = len(logs)
        if total == 0:
            return SearchAnalyticsDTO(
                total_searches=0,
                avg_dense_candidates=0.0,
                avg_sparse_candidates=0.0,
                avg_merged_unique=0.0,
                avg_retrieval_duration_ms=0.0,
                stage_breakdowns={},
            )

        avg_dense = round(sum(l.dense_candidate_count for l in logs) / total, 2)
        avg_sparse = round(sum(l.sparse_candidate_count for l in logs) / total, 2)
        avg_merged = round(sum(l.merged_unique_count for l in logs) / total, 2)
        avg_duration = round(sum(l.total_duration_ms for l in logs) / total, 2)

        return SearchAnalyticsDTO(
            total_searches=total,
            avg_dense_candidates=avg_dense,
            avg_sparse_candidates=avg_sparse,
            avg_merged_unique=avg_merged,
            avg_retrieval_duration_ms=avg_duration,
            stage_breakdowns={
                "dense_avg": avg_dense,
                "sparse_avg": avg_sparse,
                "rrf_avg": avg_merged,
            },
        )
