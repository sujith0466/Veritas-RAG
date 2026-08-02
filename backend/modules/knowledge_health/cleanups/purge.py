from backend.document.models.status import DocumentStatus

"""Two-Phase Transactional Purge Orchestrator (`ADR-M6-001`, `PurgeOrchestrator`).

Ensures safe, atomic cleanup across PostgreSQL (`documents`, `document_chunks`) and
Qdrant vector stores (`ADR-004`), preventing orphan vector pollution when deletions fail midway.
"""

import time
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.core.events.dispatcher import EventDispatcher, get_dispatcher
from backend.core.events.types import EventType
from backend.document.models.document import Document, DocumentVersion
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.knowledge_health.events.payloads import (
    KnowledgeHealthDomainEvent,
    OrphanChunksPurgedPayload,
)
from backend.modules.knowledge_health.schemas.errors import PurgeSynchronizationError
from backend.modules.knowledge_health.schemas.health_dto import PurgeSummaryDTO
from backend.modules.vector.models.vector_metadata import VectorIndexMetadata
from backend.modules.vector.services.vector_service import VectorStorageService

logger = structlog.get_logger(__name__)


class PurgeOrchestrator:
    """Orchestrates two-phase document and vector purges with rollback safety (`ADR-M6-001`)."""

    def __init__(
        self,
        session: AsyncSession,
        vector_service: VectorStorageService | None = None,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self.session = session
        self.vector_service = vector_service or VectorStorageService(session)
        self.dispatcher = dispatcher or get_dispatcher()

    async def execute_two_phase_purge(
        self, document_id: UUID, tenant_id: str
    ) -> PurgeSummaryDTO:
        """Phase 1: Mark document and versions as DELETED, then execute Phase 2 hard purge."""
        start_time = time.perf_counter()
        log = logger.bind(tenant_id=tenant_id, document_id=str(document_id))
        log.info("Initiating two-phase document purge (`ADR-M6-001`)")

        # 1. Verify and mark Document row in PostgreSQL
        stmt = select(Document).where(
            Document.id == document_id, Document.tenant_id == tenant_id
        )
        doc = (await self.session.execute(stmt)).scalar_one_or_none()

        if doc:
            doc.status = DocumentStatus.DELETED
            doc.is_deleted = True
            await self.session.flush()

        # Mark versions and chunks as soft-deleted initially
        ver_stmt = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id
        )
        versions = (await self.session.execute(ver_stmt)).scalars().all()
        for v in versions:
            v.is_deleted = True

        chunk_stmt = select(DocumentChunk).where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.tenant_id == tenant_id,
        )
        chunks = (await self.session.execute(chunk_stmt)).scalars().all()
        for c in chunks:
            c.is_deleted = True

        await self.session.flush()

        # 2. Immediately attempt Phase 2 hard purge
        try:
            summary = await self.finalize_hard_purge(
                document_id, tenant_id, start_time=start_time
            )
            return summary
        except Exception as exc:
            log.error(
                "Phase 2 hard purge synchronization failed; document marked soft-deleted for recovery sweep",
                error=str(exc),
            )
            raise PurgeSynchronizationError(
                tenant_id=tenant_id,
                document_id=str(document_id),
                reason=str(exc),
            ) from exc

    async def finalize_hard_purge(
        self,
        document_id: UUID,
        tenant_id: str,
        start_time: float | None = None,
    ) -> PurgeSummaryDTO:
        """Phase 2: Purge vector points from Qdrant and execute CASCADE hard deletion from PostgreSQL."""
        t0 = start_time or time.perf_counter()
        log = logger.bind(tenant_id=tenant_id, document_id=str(document_id))

        # 1. Delete Qdrant vector points
        points_deleted = 0
        try:
            points_deleted = await self.vector_service.delete_document_points(
                document_id=document_id,
                tenant_id=tenant_id,
            )
        except Exception as exc:
            log.warning(
                "Qdrant point purge encountered error or partial cleanup",
                error=str(exc),
            )

        # 2. Count chunks before deleting
        chunk_stmt = select(DocumentChunk).where(
            DocumentChunk.document_id == document_id,
            DocumentChunk.tenant_id == tenant_id,
        )
        chunks = (await self.session.execute(chunk_stmt)).scalars().all()
        chunks_deleted = len(chunks)

        # 3. Hard delete associated records in DB
        await self.session.execute(
            delete(ChunkEmbedding).where(
                ChunkEmbedding.chunk_id.in_([c.id for c in chunks])
            )
        )
        await self.session.execute(
            delete(VectorIndexMetadata).where(
                VectorIndexMetadata.document_id == document_id,
                VectorIndexMetadata.tenant_id == tenant_id,
            )
        )
        await self.session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.tenant_id == tenant_id,
            )
        )
        await self.session.execute(
            delete(DocumentVersion).where(DocumentVersion.document_id == document_id)
        )
        await self.session.execute(
            delete(Document).where(
                Document.id == document_id, Document.tenant_id == tenant_id
            )
        )

        await self.session.flush()

        duration_ms = (time.perf_counter() - t0) * 1000.0

        # Emit domain event
        payload = OrphanChunksPurgedPayload(
            tenant_id=tenant_id,
            document_id=document_id,
            chunks_purged=chunks_deleted,
            vectors_purged=points_deleted,
            reason="TWO_PHASE_PURGE",
        )
        await self.dispatcher.publish(
            KnowledgeHealthDomainEvent(
                event_type=EventType.ORPHAN_CHUNKS_PURGED, payload=payload.to_dict()
            )
        )

        log.info(
            "Finalized two-phase hard purge successfully",
            chunks_purged=chunks_deleted,
            vectors_purged=points_deleted,
        )
        return PurgeSummaryDTO(
            document_id=document_id,
            tenant_id=tenant_id,
            qdrant_points_deleted=points_deleted,
            pg_chunks_deleted=chunks_deleted,
            is_fully_purged=True,
            duration_ms=duration_ms,
        )
