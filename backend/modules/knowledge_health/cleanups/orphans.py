"""Orphan Cleanup Engine (`OrphanCleanupEngine`).

Sweeps and purges unreferenced chunks and vector points lacking valid parent documents,
preventing phantom retrieval results and storage bloat (`ADR-M6-001`).
"""

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.models.document import Document
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.vector.models.vector_metadata import VectorIndexMetadata
from backend.modules.vector.services.vector_service import VectorStorageService

logger = structlog.get_logger(__name__)


class OrphanCleanupEngine:
    """Automated garbage collector auditing and purging orphaned records and vector points."""

    def __init__(
        self,
        session: AsyncSession,
        vector_service: VectorStorageService | None = None,
    ) -> None:
        self.session = session
        self.vector_service = vector_service or VectorStorageService(session)

    async def sweep_orphaned_chunks(self, tenant_id: str) -> int:
        """Find and purge chunks lacking valid parent documents or belonging to soft-deleted documents."""
        log = logger.bind(tenant_id=tenant_id)
        log.info("Starting orphan chunk sweep")

        # 1. Identify active documents for this tenant
        doc_stmt = select(Document.id).where(
            Document.tenant_id == tenant_id,
            Document.is_deleted.is_(False),
            Document.status != "DELETED",
        )
        active_doc_ids = set((await self.session.execute(doc_stmt)).scalars().all())

        # 2. Find chunks in this tenant whose document_id is not in active_doc_ids or marked is_deleted
        chunk_stmt = select(DocumentChunk).where(DocumentChunk.tenant_id == tenant_id)
        all_chunks = (await self.session.execute(chunk_stmt)).scalars().all()

        orphaned_chunks = [
            c for c in all_chunks if c.document_id not in active_doc_ids or c.is_deleted
        ]

        if not orphaned_chunks:
            log.info("Zero orphaned chunks found during sweep")
            return 0

        # Group orphaned chunks by document_id to clean up Qdrant points efficiently
        doc_ids_to_purge = {c.document_id for c in orphaned_chunks}
        for doc_id in doc_ids_to_purge:
            try:
                await self.vector_service.delete_document_points(
                    document_id=doc_id, tenant_id=tenant_id
                )
            except Exception as exc:
                log.warning(
                    "Partial Qdrant point cleanup during orphan sweep",
                    document_id=str(doc_id),
                    error=str(exc),
                )

        orphan_chunk_ids = [c.id for c in orphaned_chunks]

        # 3. Hard delete associated chunk_embeddings, vector_index_metadata, and document_chunks
        await self.session.execute(
            delete(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(orphan_chunk_ids))
        )
        await self.session.execute(
            delete(VectorIndexMetadata).where(
                VectorIndexMetadata.document_id.in_(list(doc_ids_to_purge)),
                VectorIndexMetadata.tenant_id == tenant_id,
            )
        )
        await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.id.in_(orphan_chunk_ids))
        )

        await self.session.flush()
        purged_count = len(orphaned_chunks)
        log.info(
            "Completed orphan chunk sweep",
            purged_count=purged_count,
            affected_docs=len(doc_ids_to_purge),
        )
        return purged_count

    async def sweep_orphaned_vectors(self, tenant_id: str) -> int:
        """Alias and extension of chunk sweep to clean unreferenced vector points."""
        return await self.sweep_orphaned_chunks(tenant_id)
