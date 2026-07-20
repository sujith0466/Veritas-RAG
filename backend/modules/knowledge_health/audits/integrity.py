"""Integrity Auditor (`IntegrityAuditor`).

Verifies 1:1 count parity between active PostgreSQL DocumentChunks and indexed Qdrant vector points,
detecting drift and emitting telemetry (`ADR-M6-001`).
"""

from datetime import datetime, timezone
from typing import Optional
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.events.dispatcher import EventDispatcher, get_dispatcher
from backend.core.events.base import BaseEvent
from backend.core.events.types import EventType
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.knowledge_health.events.payloads import KnowledgeDriftDetectedPayload, KnowledgeHealthDomainEvent
from backend.modules.knowledge_health.schemas.health_dto import ParityAuditDTO
from backend.modules.vector.models.vector_metadata import VectorIndexMetadata
from backend.modules.vector.providers.base import BaseVectorDBProvider
from backend.modules.vector.providers.factory import VectorProviderFactory

logger = structlog.get_logger(__name__)


class IntegrityAuditor:
    """Audits 1:1 count parity across PostgreSQL and Qdrant storage tiers."""

    def __init__(
        self,
        session: AsyncSession,
        provider: Optional[BaseVectorDBProvider] = None,
        dispatcher: Optional[EventDispatcher] = None,
    ) -> None:
        self.session = session
        self.provider = provider or VectorProviderFactory.get_provider("qdrant")
        self.dispatcher = dispatcher or get_dispatcher()

    async def verify_tenant_parity(self, tenant_id: str) -> ParityAuditDTO:
        """Count active embedded chunks in DB vs total points indexed across active Qdrant collections."""
        log = logger.bind(tenant_id=tenant_id)
        log.info("Starting 1:1 count parity audit")

        # 1. Count embedded chunks in PostgreSQL
        stmt = select(func.count(DocumentChunk.id)).where(
            DocumentChunk.tenant_id == tenant_id,
            DocumentChunk.is_embedded.is_(True),
            DocumentChunk.is_deleted.is_(False),
        )
        pg_count_res = await self.session.execute(stmt)
        pg_count = pg_count_res.scalar_one_or_none() or 0

        # 2. Discover active collections for this tenant from VectorIndexMetadata
        meta_stmt = select(VectorIndexMetadata.collection_name).where(
            VectorIndexMetadata.tenant_id == tenant_id,
            VectorIndexMetadata.is_deleted.is_(False),
        ).distinct()
        cols = (await self.session.execute(meta_stmt)).scalars().all()
        collection_names = list(cols) if cols else ["raguard_knowledge_1536"]

        qdrant_count = 0
        for col in collection_names:
            try:
                info = await self.provider.get_collection_info(col)
                qdrant_count += info.points_count
            except Exception as exc:
                log.warning("Could not fetch collection info during parity check", collection=col, error=str(exc))

        is_synced = (pg_count == qdrant_count)
        if is_synced:
            parity_status = f"SYNCED ({pg_count} == {qdrant_count})"
        else:
            parity_status = f"MISMATCH_DETECTED ({pg_count} DB != {qdrant_count} Qdrant)"
            log.warning("Parity mismatch detected between PostgreSQL and Qdrant", pg_count=pg_count, qdrant_count=qdrant_count)
            payload = KnowledgeDriftDetectedPayload(
                tenant_id=tenant_id,
                drift_type="PARITY_MISMATCH",
                details={
                    "pg_chunk_count": pg_count,
                    "qdrant_point_count": qdrant_count,
                    "collections_checked": collection_names,
                },
            )
            await self.dispatcher.publish(
                KnowledgeHealthDomainEvent(event_type=EventType.KNOWLEDGE_DRIFT_DETECTED, payload=payload.to_dict())
            )

        return ParityAuditDTO(
            tenant_id=tenant_id,
            pg_chunk_count=pg_count,
            qdrant_point_count=qdrant_count,
            is_synced=is_synced,
            parity_status=parity_status,
            checked_at=datetime.now(timezone.utc),
        )
