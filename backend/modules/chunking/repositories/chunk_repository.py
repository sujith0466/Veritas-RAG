"""Document Chunk Repository (`DocumentChunkRepository`)."""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.chunking.schemas.chunk import ChunkMetricsDTO
from backend.repositories.base import BaseRepository


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    """Async repository managing database operations for `DocumentChunk` entities."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DocumentChunk)

    async def get_by_id_and_tenant(
        self, chunk_id: uuid.UUID, tenant_id: str
    ) -> DocumentChunk | None:
        """Fetch a single chunk by ID and tenant ID with relationships eagerly loaded."""
        stmt = (
            select(DocumentChunk)
            .where(
                DocumentChunk.id == chunk_id,
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.is_deleted.is_(False),
            )
            .options(
                selectinload(DocumentChunk.previous_chunk),
                selectinload(DocumentChunk.next_chunk),
                selectinload(DocumentChunk.parent_chunk),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_chunks_by_version(
        self,
        tenant_id: str,
        document_version_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        strategy_used: str | None = None,
    ) -> Sequence[DocumentChunk]:
        """Fetch paginated chunks for a specific document version ordered sequentially."""
        stmt = select(DocumentChunk).where(
            DocumentChunk.tenant_id == tenant_id,
            DocumentChunk.document_version_id == document_version_id,
            DocumentChunk.is_deleted.is_(False),
        )
        if strategy_used:
            stmt = stmt.where(DocumentChunk.strategy_used == strategy_used)

        stmt = stmt.order_by(DocumentChunk.chunk_index.asc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_chunks_by_version(
        self,
        tenant_id: str,
        document_version_id: uuid.UUID,
        strategy_used: str | None = None,
    ) -> int:
        """Count active chunks belonging to a document version."""
        stmt = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.document_version_id == document_version_id,
                DocumentChunk.is_deleted.is_(False),
            )
        )
        if strategy_used:
            stmt = stmt.where(DocumentChunk.strategy_used == strategy_used)
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def get_chunks_by_document(
        self,
        tenant_id: str,
        document_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        strategy_used: str | None = None,
    ) -> Sequence[DocumentChunk]:
        """Fetch paginated chunks for all or latest version of a document."""
        stmt = select(DocumentChunk).where(
            DocumentChunk.tenant_id == tenant_id,
            DocumentChunk.document_id == document_id,
            DocumentChunk.is_deleted.is_(False),
        )
        if strategy_used:
            stmt = stmt.where(DocumentChunk.strategy_used == strategy_used)

        stmt = (
            stmt.order_by(
                DocumentChunk.document_version_id, DocumentChunk.chunk_index.asc()
            )
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_chunks_by_document(
        self,
        tenant_id: str,
        document_id: uuid.UUID,
        strategy_used: str | None = None,
    ) -> int:
        """Count active chunks belonging to a document across versions."""
        stmt = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.document_id == document_id,
                DocumentChunk.is_deleted.is_(False),
            )
        )
        if strategy_used:
            stmt = stmt.where(DocumentChunk.strategy_used == strategy_used)
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def batch_create_chunks(
        self, chunks: list[DocumentChunk]
    ) -> list[DocumentChunk]:
        """Bulk add chunk instances to session (`ADR-005`)."""
        if not chunks:
            return []
        self.session.add_all(chunks)
        await self.session.flush()
        return chunks

    async def delete_chunks_by_version(
        self, tenant_id: str, document_version_id: uuid.UUID
    ) -> int:
        """Hard delete chunks for a specific document version before re-chunking."""
        stmt = delete(DocumentChunk).where(
            DocumentChunk.tenant_id == tenant_id,
            DocumentChunk.document_version_id == document_version_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0

    async def delete_chunks_by_document(
        self, tenant_id: str, document_id: uuid.UUID
    ) -> int:
        """Hard delete all chunks for a document namespace."""
        stmt = delete(DocumentChunk).where(
            DocumentChunk.tenant_id == tenant_id,
            DocumentChunk.document_id == document_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0

    async def get_chunk_metrics(
        self,
        tenant_id: str | None = None,
        document_id: uuid.UUID | None = None,
    ) -> ChunkMetricsDTO:
        """Aggregate summary metrics across chunks (`ADR-005`)."""
        stmt = select(
            func.count(DocumentChunk.id),
            func.sum(DocumentChunk.character_count),
            func.sum(DocumentChunk.token_count),
            func.avg(DocumentChunk.character_count),
            func.avg(DocumentChunk.token_count),
            func.sum(sa.case((DocumentChunk.is_embedded.is_(True), 1), else_=0)),
        ).where(DocumentChunk.is_deleted.is_(False))

        if tenant_id:
            stmt = stmt.where(DocumentChunk.tenant_id == tenant_id)
        if document_id:
            stmt = stmt.where(DocumentChunk.document_id == document_id)

        result = await self.session.execute(stmt)
        row = result.fetchone()

        total_chunks = row[0] or 0 if row else 0
        total_chars = int(row[1] or 0) if row else 0
        total_tokens = int(row[2] or 0) if row else 0
        avg_chars = float(row[3] or 0.0) if row else 0.0
        avg_tokens = float(row[4] or 0.0) if row else 0.0
        embedded_count = int(row[5] or 0) if row else 0

        # Group by strategy breakdown
        strat_stmt = (
            select(DocumentChunk.strategy_used, func.count(DocumentChunk.id))
            .where(DocumentChunk.is_deleted.is_(False))
            .group_by(DocumentChunk.strategy_used)
        )
        if tenant_id:
            strat_stmt = strat_stmt.where(DocumentChunk.tenant_id == tenant_id)
        if document_id:
            strat_stmt = strat_stmt.where(DocumentChunk.document_id == document_id)

        strat_result = await self.session.execute(strat_stmt)
        strategy_breakdown = {s: c for s, c in strat_result.fetchall()}

        return ChunkMetricsDTO(
            total_chunks=total_chunks,
            total_characters=total_chars,
            total_tokens=total_tokens,
            average_chunk_characters=avg_chars,
            average_chunk_tokens=avg_tokens,
            strategy_breakdown=strategy_breakdown,
            is_embedded_count=embedded_count,
        )
