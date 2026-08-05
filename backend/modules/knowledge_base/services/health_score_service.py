from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import case as sa_case
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.models import Document, DocumentVersion
from backend.document.models.failed_job import FailedJob
from backend.modules.chunking.models import DocumentChunk
from backend.modules.knowledge_base.schemas.health_score_dto import (
    DimensionScoreDTO,
    KnowledgeHealthScoreDTO,
)


class KnowledgeHealthScoreService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_workspace_health(self, workspace_id: UUID) -> KnowledgeHealthScoreDTO:
        # Dimensions
        coverage = await self._calculate_coverage(workspace_id)
        freshness = await self._calculate_freshness(workspace_id)
        quality = await self._calculate_quality(workspace_id)
        reliability = await self._calculate_reliability(workspace_id)

        # Composite score
        overall_score = (
            coverage.score * coverage.weight
            + freshness.score * freshness.weight
            + quality.score * quality.weight
            + reliability.score * reliability.weight
        )

        tier = self._determine_tier(overall_score)
        recommendations = self._generate_recommendations(
            coverage, freshness, quality, reliability, overall_score
        )

        return KnowledgeHealthScoreDTO(
            workspace_id=workspace_id,
            overall_score=round(overall_score, 2),
            tier=tier,
            coverage=coverage,
            freshness=freshness,
            quality=quality,
            reliability=reliability,
            prioritized_recommendations=recommendations,
        )

    async def _calculate_coverage(self, workspace_id: UUID) -> DimensionScoreDTO:
        """
        Coverage (30%): Successfully processed & vectorized vs total docs.
        """
        stmt = select(
            func.count(Document.id).label("total"),
            func.sum(
                func.cast(Document.status == "INDEXED", func.Integer())  # Assuming INDEXED means processed
            ).label("indexed")
        ).where(
            Document.tenant_id == workspace_id,
            not Document.is_deleted
        )

        # We need sa_case here. Let's rewrite safely.
        from sqlalchemy import case as sa_case
        stmt = select(
            func.count(Document.id).label("total"),
            func.sum(sa_case((Document.status == "INDEXED", 1), else_=0)).label("indexed")
        ).where(
            Document.tenant_id == workspace_id,
            not Document.is_deleted
        )

        res = await self.session.execute(stmt)
        total, indexed = res.one_or_none() or (0, 0)
        total = total or 0
        indexed = indexed or 0

        score = 100.0 if total == 0 else (indexed / total) * 100.0

        return DimensionScoreDTO(
            score=round(score, 2),
            weight=0.30,
            raw_metric=indexed / total if total > 0 else 1.0,
            description=f"{indexed}/{total} documents successfully indexed.",
        )

    async def _calculate_freshness(self, workspace_id: UUID) -> DimensionScoreDTO:
        """
        Freshness (25%): Average freshness_score across active documents.
        """
        stmt = select(Document.user_metadata).where(
            Document.tenant_id == workspace_id,
            not Document.is_deleted
        )
        res = await self.session.execute(stmt)
        docs = res.scalars().all()

        if not docs:
            return DimensionScoreDTO(
                score=100.0,
                weight=0.25,
                raw_metric=100.0,
                description="No documents to evaluate for freshness.",
            )

        total_score = 0.0
        for md in docs:
            total_score += md.get("freshness_score", 100.0) if md else 100.0

        avg_score = total_score / len(docs)

        return DimensionScoreDTO(
            score=round(avg_score, 2),
            weight=0.25,
            raw_metric=avg_score,
            description=f"Average freshness decay score is {round(avg_score, 1)}%.",
        )

    async def _calculate_quality(self, workspace_id: UUID) -> DimensionScoreDTO:
        """
        Quality (25%): Penalties for empty chunks, variance, OCR confidence.
        """
        # For simplicity in this mock calculation, we check the ratio of non-empty chunks.
        # In a real scenario, this would query chunk lengths or OCR metadata.
        stmt = (
            select(
                func.count(DocumentChunk.id).label("total"),
                func.sum(sa_case((DocumentChunk.token_count < 10, 1), else_=0)).label("low_quality")
            )
            .join(DocumentVersion, DocumentChunk.document_version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                Document.tenant_id == workspace_id,
                not Document.is_deleted,
                Document.active_version_id == DocumentVersion.id
            )
        )
        res = await self.session.execute(stmt)
        total_chunks, low_quality = res.one_or_none() or (0, 0)
        total_chunks = total_chunks or 0
        low_quality = low_quality or 0

        if total_chunks == 0:
            score = 100.0
        else:
            penalty = (low_quality / total_chunks) * 100.0
            score = max(0.0, 100.0 - penalty)

        return DimensionScoreDTO(
            score=round(score, 2),
            weight=0.25,
            raw_metric=total_chunks - low_quality,
            description=f"{low_quality} low-quality chunks out of {total_chunks}.",
        )

    async def _calculate_reliability(self, workspace_id: UUID) -> DimensionScoreDTO:
        """
        Reliability (20%): Failed job / DLQ error rate over the last 30 days.
        """
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        stmt_failed = select(func.count(FailedJob.id)).where(
            FailedJob.workspace_id == workspace_id,
            FailedJob.created_at >= thirty_days_ago
        )
        res_failed = await self.session.execute(stmt_failed)
        failed_count = res_failed.scalar() or 0

        # Penalize score by 5 points for each failure in the last 30 days, up to 100
        penalty = min(100.0, failed_count * 5.0)
        score = 100.0 - penalty

        return DimensionScoreDTO(
            score=round(score, 2),
            weight=0.20,
            raw_metric=failed_count,
            description=f"{failed_count} pipeline failures in the last 30 days.",
        )

    def _determine_tier(self, score: float) -> str:
        if score >= 90:
            return "EXCELLENT"
        if score >= 75:
            return "GOOD"
        if score >= 50:
            return "DEGRADED"
        return "CRITICAL"

    def _generate_recommendations(
        self,
        coverage: DimensionScoreDTO,
        freshness: DimensionScoreDTO,
        quality: DimensionScoreDTO,
        reliability: DimensionScoreDTO,
        _overall_score: float,
    ) -> list[str]:
        recommendations = []
        if coverage.score < 80:
            recommendations.append("Investigate documents that failed to index or are stuck in processing.")
        if freshness.score < 80:
            recommendations.append("Review stale documents and archive or reprocess them.")
        if quality.score < 80:
            recommendations.append("Adjust chunking strategies; many small or low-quality chunks detected.")
        if reliability.score < 80:
            recommendations.append("High pipeline failure rate detected. Review DLQ and reprocess failed jobs.")

        if not recommendations:
            recommendations.append("Knowledge base is healthy. No immediate action required.")

        return recommendations
