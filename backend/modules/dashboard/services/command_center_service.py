"""Command Center Service (`DASH-002`).

Aggregates enterprise AI reliability telemetry, latency percentiles,
subsystem health, knowledge-base status, and time-series trends.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import time
from uuid import uuid4

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.cache.client import check_cache_health
from backend.database.engine import check_db_health
from backend.document.models.document import Document
from backend.document.models.job import ProcessingJob
from backend.document.models.status import DocumentStatus
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.modules.analytics.models.query_analytics import QueryAnalyticsRecord
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.dashboard.schemas.dashboard_dto import (
    CommandCenterDTO,
    CommandHealthComponentDTO,
    CommandKnowledgeHealthDTO,
    CommandKpisDTO,
    CommandLatencyPercentilesDTO,
    CommandOutcomesBreakdownDTO,
    CommandReliabilityTrendPointDTO,
    CommandSystemHealthDTO,
    ExecutiveDashboardAlertDTO,
)
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.vector_db.client import check_vector_db_health

logger = structlog.get_logger(__name__)


class CommandCenterService:
    """Service responsible for aggregating enterprise AI reliability command center telemetry."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_command_center(
        self, tenant_id: str, time_window: str = "24h"
    ) -> CommandCenterDTO:
        """Consolidate high-integrity telemetry across all reliable RAG operational subsystems."""
        t_start = time.perf_counter()
        now_utc = datetime.now(UTC)

        # 1. Resolve cutoff
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

        # 2. Probe System Health
        components: list[CommandHealthComponentDTO] = []
        overall_status = "OPERATIONAL"

        # Database health
        try:
            t0 = time.perf_counter()
            db_ok = await check_db_health()
            db_lat = (time.perf_counter() - t0) * 1000
            components.append(
                CommandHealthComponentDTO(
                    name="PostgreSQL",
                    status="healthy" if db_ok else "unhealthy",
                    latency_ms=round(db_lat, 2),
                    detail="Primary relational store & analytics telemetry",
                )
            )
            if not db_ok:
                overall_status = "OUTAGE"
        except Exception as exc:
            logger.warning("Error checking DB health", error=str(exc))
            overall_status = "OUTAGE"
            components.append(
                CommandHealthComponentDTO(
                    name="PostgreSQL",
                    status="unhealthy",
                    detail=f"Connection failed: {exc}",
                )
            )

        # Redis health
        try:
            cache_info = await check_cache_health()
            cache_ok = cache_info.get("status") == "healthy"
            components.append(
                CommandHealthComponentDTO(
                    name="Redis",
                    status="healthy" if cache_ok else "degraded",
                    latency_ms=cache_info.get("latency_ms"),
                    detail="Distributed cache & task broker",
                )
            )
            if not cache_ok and overall_status == "OPERATIONAL":
                overall_status = "DEGRADED"
        except Exception as exc:
            logger.warning("Error checking cache health", error=str(exc))
            if overall_status == "OPERATIONAL":
                overall_status = "DEGRADED"
            components.append(
                CommandHealthComponentDTO(
                    name="Redis",
                    status="degraded",
                    detail=f"Cache check error: {exc}",
                )
            )

        # Vector DB health
        vector_cluster_status = "green"
        try:
            v_res = await check_vector_db_health()
            v_ok = v_res.get("status") == "healthy"
            vector_cluster_status = "green" if v_ok else "yellow"
            components.append(
                CommandHealthComponentDTO(
                    name="Qdrant Vector Cluster",
                    status="healthy" if v_ok else "degraded",
                    latency_ms=v_res.get("latency_ms"),
                    detail="Dense & sparse index collection store",
                )
            )
            if not v_ok and overall_status == "OPERATIONAL":
                overall_status = "DEGRADED"
        except Exception as exc:
            logger.warning("Error checking vector DB health", error=str(exc))
            vector_cluster_status = "yellow"
            components.append(
                CommandHealthComponentDTO(
                    name="Qdrant Vector Cluster",
                    status="degraded",
                    detail=f"Vector DB probe warning: {exc}",
                )
            )

        system_health = CommandSystemHealthDTO(
            status=overall_status,
            components=components,
        )

        # 3. Query Execution KPIs & Latency Percentiles
        stats_query = select(
            func.count(QueryAnalyticsRecord.id),
            func.avg(QueryAnalyticsRecord.confidence_score),
            func.avg(QueryAnalyticsRecord.reliability_score),
            func.avg(QueryAnalyticsRecord.total_duration_ms),
            func.percentile_cont(0.50).within_group(QueryAnalyticsRecord.total_duration_ms),
            func.percentile_cont(0.90).within_group(QueryAnalyticsRecord.total_duration_ms),
            func.percentile_cont(0.95).within_group(QueryAnalyticsRecord.total_duration_ms),
            func.percentile_cont(0.99).within_group(QueryAnalyticsRecord.total_duration_ms),
            func.sum(case((QueryAnalyticsRecord.retry_attempts > 0, 1), else_=0)),
        ).where(QueryAnalyticsRecord.tenant_id == tenant_id)

        if cutoff is not None:
            stats_query = stats_query.where(QueryAnalyticsRecord.created_at >= cutoff)

        stats_result = await self._session.execute(stats_query)
        (
            total_queries,
            avg_conf,
            avg_rel,
            avg_lat,
            p50_lat,
            p90_lat,
            p95_lat,
            p99_lat,
            retries_count,
        ) = stats_result.first() or (0, None, None, None, None, None, None, None, 0)

        total_queries = total_queries or 0
        retries_count = retries_count or 0

        # Semantically correct empty states
        if total_queries > 0:
            avg_confidence_score = float(avg_conf) if avg_conf is not None else None
            avg_reliability_score = float(avg_rel) if avg_rel is not None else None
            avg_latency_ms = float(avg_lat) if avg_lat is not None else None
            p50_ms = float(p50_lat) if p50_lat is not None else None
            p90_ms = float(p90_lat) if p90_lat is not None else None
            p95_ms = float(p95_lat) if p95_lat is not None else None
            p99_ms = float(p99_lat) if p99_lat is not None else None
            self_correction_rate = round((retries_count / total_queries) * 100.0, 2)
        else:
            avg_confidence_score = None
            avg_reliability_score = None
            avg_latency_ms = None
            p50_ms = None
            p90_ms = None
            p95_ms = None
            p99_ms = None
            self_correction_rate = 0.0

        latency_percentiles = CommandLatencyPercentilesDTO(
            p50_ms=p50_ms,
            p90_ms=p90_ms,
            p95_ms=p95_ms,
            p99_ms=p99_ms,
            avg_ms=avg_latency_ms,
        )

        # 4. Outcomes Breakdown
        outcomes_query = (
            select(QueryAnalyticsRecord.outcome, func.count(QueryAnalyticsRecord.id))
            .where(QueryAnalyticsRecord.tenant_id == tenant_id)
        )
        if cutoff is not None:
            outcomes_query = outcomes_query.where(QueryAnalyticsRecord.created_at >= cutoff)
        outcomes_query = outcomes_query.group_by(QueryAnalyticsRecord.outcome)

        outcomes_result = await self._session.execute(outcomes_query)
        outcomes_map = {row[0]: row[1] for row in outcomes_result.all() if row[0]}

        success_count = outcomes_map.get("SUCCESS", 0)
        aborted_hallucination = outcomes_map.get("ABORTED_HALLUCINATION", 0)
        aborted_low_conf = outcomes_map.get("ABORTED_LOW_CONFIDENCE", 0)
        clarification_count = outcomes_map.get("CLARIFICATION_REQUIRED", 0)
        no_relevant_chunks = outcomes_map.get("NO_RELEVANT_CHUNKS", 0)
        policy_violation = outcomes_map.get("POLICY_VIOLATION", 0)
        clarification_rate = (
            round((clarification_count / total_queries) * 100.0, 2)
            if total_queries > 0
            else 0.0
        )

        outcomes = CommandOutcomesBreakdownDTO(
            success_count=success_count,
            aborted_hallucination_count=aborted_hallucination,
            aborted_low_confidence_count=aborted_low_conf,
            clarification_count=clarification_count,
            no_relevant_chunks_count=no_relevant_chunks,
            policy_violation_count=policy_violation,
            total_count=total_queries,
        )

        # 5. Multi-Tenant Boundary Telemetry (Strictly scoped to tenant_id)
        # Prevents cross-tenant aggregate disclosure under Enterprise Isolation Policy
        active_tenants = 1

        try:
            ws_res = await self._session.execute(
                select(func.count(func.distinct(WorkspaceMember.workspace_id)))
                .join(User, WorkspaceMember.user_id == User.id)
                .join(Workspace, WorkspaceMember.workspace_id == Workspace.id)
                .where(
                    User.tenant_id == tenant_id,
                    Workspace.status == WorkspaceStatus.ACTIVE.value,
                    WorkspaceMember.status == MemberStatus.ACTIVE.value,
                )
            )
            count = ws_res.scalar()
            active_workspaces = count if (count is not None and count > 0) else 1
        except Exception:
            active_workspaces = 1

        kpis = CommandKpisDTO(
            total_queries=total_queries,
            avg_reliability_score=avg_reliability_score,
            avg_confidence_score=avg_confidence_score,
            avg_latency_ms=avg_latency_ms,
            p95_latency_ms=p95_ms,
            self_correction_rate=self_correction_rate,
            clarification_rate=clarification_rate,
            hallucination_prevention_count=aborted_hallucination + aborted_low_conf,
            active_tenants=active_tenants,
            active_workspaces=active_workspaces,
        )

        # 6. Reliability & Volume Trend Time-Series
        interval = "hour" if time_window in ("1h", "24h") else "day"
        trend_query = (
            select(
                func.date_trunc(interval, QueryAnalyticsRecord.created_at).label("bucket"),
                func.avg(QueryAnalyticsRecord.reliability_score).label("avg_rel"),
                func.count(QueryAnalyticsRecord.id).label("q_count"),
            )
            .where(QueryAnalyticsRecord.tenant_id == tenant_id)
        )
        if cutoff is not None:
            trend_query = trend_query.where(QueryAnalyticsRecord.created_at >= cutoff)
        trend_query = trend_query.group_by("bucket").order_by("bucket")

        trend_res = await self._session.execute(trend_query)
        reliability_trend: list[CommandReliabilityTrendPointDTO] = []
        for row in trend_res.all():
            bucket, r_avg, q_c = row
            if bucket:
                reliability_trend.append(
                    CommandReliabilityTrendPointDTO(
                        timestamp=bucket.isoformat(),
                        reliability=round(float(r_avg or 0.0) * 100.0, 1),
                        query_count=q_c or 0,
                    )
                )

        # 7. Knowledge Base & Ingestion Pipeline Health
        doc_query = select(
            func.count(Document.id),
            func.sum(case((Document.status == DocumentStatus.READY, 1), else_=0)),
            func.sum(case((Document.status == DocumentStatus.FAILED, 1), else_=0)),
        ).where(Document.tenant_id == tenant_id)
        doc_res = await self._session.execute(doc_query)
        total_docs, processed_docs, failed_docs = doc_res.first() or (0, 0, 0)

        chunk_res = await self._session.execute(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.tenant_id == tenant_id)
        )
        total_chunks = chunk_res.scalar() or 0

        emb_res = await self._session.execute(
            select(func.count(ChunkEmbedding.id)).where(ChunkEmbedding.tenant_id == tenant_id)
        )
        total_embeddings = emb_res.scalar() or 0

        job_query = (
            select(
                func.sum(case((ProcessingJob.status == "PENDING", 1), else_=0)),
                func.sum(case((ProcessingJob.status == "FAILED", 1), else_=0)),
            )
            .join(Document, ProcessingJob.document_id == Document.id)
            .where(Document.tenant_id == tenant_id)
        )
        job_res = await self._session.execute(job_query)
        pending_jobs, failed_jobs = job_res.first() or (0, 0)

        knowledge_health = CommandKnowledgeHealthDTO(
            total_documents=total_docs or 0,
            processed_documents=processed_docs or 0,
            failed_documents=failed_docs or 0,
            total_chunks=total_chunks or 0,
            total_embeddings=total_embeddings or 0,
            pending_jobs=pending_jobs or 0,
            failed_jobs=failed_jobs or 0,
            vector_status=vector_cluster_status,
        )

        # 8. Security & Anomaly Alerts
        alerts_query = (
            select(QueryAnalyticsRecord)
            .where(
                QueryAnalyticsRecord.tenant_id == tenant_id,
                QueryAnalyticsRecord.outcome.in_(
                    ("ABORTED_HALLUCINATION", "ABORTED_LOW_CONFIDENCE", "POLICY_VIOLATION")
                ),
            )
        )
        if cutoff is not None:
            alerts_query = alerts_query.where(QueryAnalyticsRecord.created_at >= cutoff)
        alerts_query = alerts_query.order_by(QueryAnalyticsRecord.created_at.desc()).limit(5)

        alerts_res = await self._session.execute(alerts_query)
        alerts_records = alerts_res.scalars().all()
        alerts: list[ExecutiveDashboardAlertDTO] = []

        for rec in alerts_records:
            dt_str = rec.created_at.isoformat() if rec.created_at else now_utc.isoformat()
            if rec.outcome == "POLICY_VIOLATION":
                alert_type = "SECURITY_POLICY_VIOLATION"
                sev = "HIGH"
                reason = "Input query flagged by security or DLP guardrail as policy violation."
            elif rec.outcome == "ABORTED_HALLUCINATION":
                alert_type = "HALLUCINATION_PREVENTION"
                sev = "HIGH"
                reason = "Reflection loop flagged response as ungrounded or contradictory."
            else:
                alert_type = "LOW_CONFIDENCE_INTERVENTION"
                sev = "MEDIUM"
                reason = "Retrieval confidence fell below strict generation threshold."

            alerts.append(
                ExecutiveDashboardAlertDTO(
                    id=str(uuid4()),
                    timestamp=dt_str,
                    alert_type=alert_type,
                    severity=sev,
                    query_snippet=rec.query_text[:70] + ("..." if len(rec.query_text) > 70 else ""),
                    reason=reason,
                )
            )

        duration_ms = (time.perf_counter() - t_start) * 1000
        logger.info(
            "Command center telemetry aggregated",
            tenant_id=tenant_id,
            time_window=time_window,
            duration_ms=round(duration_ms, 2),
            total_queries=total_queries,
        )

        return CommandCenterDTO(
            tenant_id=tenant_id,
            time_window=time_window,
            system_health=system_health,
            kpis=kpis,
            reliability_trend=reliability_trend,
            latency_percentiles=latency_percentiles,
            outcomes=outcomes,
            knowledge_health=knowledge_health,
            alerts=alerts,
        )
