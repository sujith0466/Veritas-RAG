"""Embedding Domain Repository (`EmbeddingRepository`).

Implements `IEmbeddingRepository` to provide high-performance database access,
bulk vector staging (`chunk_embeddings`), zero-call idempotency hash filtering,
and multi-tenant namespace isolation (`ADR-005`, `ADR-M2-001`).
"""

from collections.abc import Sequence
from typing import Any
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.embedding.models.embedding_job import EmbeddingJob
from backend.modules.embedding.repositories.base import IEmbeddingRepository
from backend.repositories.base import BaseRepository


class EmbeddingRepository(BaseRepository[EmbeddingJob], IEmbeddingRepository):
    """Async repository managing database operations for `EmbeddingJob` and `ChunkEmbedding`."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, EmbeddingJob)

    async def create_job(self, job: EmbeddingJob) -> EmbeddingJob:
        """Persist a new `EmbeddingJob` in the database."""
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get_job_by_id_and_tenant(
        self, job_id: uuid.UUID, tenant_id: str
    ) -> EmbeddingJob | None:
        """Fetch an `EmbeddingJob` by UUID ensuring tenant boundary isolation."""
        stmt = select(EmbeddingJob).where(
            EmbeddingJob.id == job_id,
            EmbeddingJob.tenant_id == tenant_id,
            EmbeddingJob.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_jobs_by_tenant(
        self,
        tenant_id: str,
        document_id: uuid.UUID | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[EmbeddingJob], int]:
        """Fetch paginated `EmbeddingJob` records and total matching count for a tenant."""
        where_clauses = [
            EmbeddingJob.tenant_id == tenant_id,
            EmbeddingJob.is_deleted.is_(False),
        ]
        if document_id:
            where_clauses.append(EmbeddingJob.document_id == document_id)
        if status:
            where_clauses.append(EmbeddingJob.status == status)

        count_stmt = (
            select(func.count()).select_from(EmbeddingJob).where(*where_clauses)
        )
        total = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = (
            select(EmbeddingJob)
            .where(*where_clauses)
            .order_by(EmbeddingJob.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return items, total

    async def update_job_progress(
        self,
        job_id: uuid.UUID,
        tenant_id: str,
        processed_delta: int = 0,
        failed_delta: int = 0,
        tokens_delta: int = 0,
        status: str | None = None,
        error_message: str | None = None,
    ) -> EmbeddingJob | None:
        """Atomically update job progress counters, tokens, and status."""
        job = await self.get_job_by_id_and_tenant(job_id, tenant_id)
        if not job:
            return None

        job.processed_chunks += processed_delta
        job.failed_chunks += failed_delta
        job.total_tokens_consumed += tokens_delta
        if status is not None:
            job.status = status
        if error_message is not None:
            job.error_message = error_message

        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get_unembedded_chunks(
        self,
        tenant_id: str,
        document_version_id: uuid.UUID,
        batch_size: int = 100,
    ) -> Sequence[DocumentChunk]:
        """Fetch up to `batch_size` unindexed `DocumentChunk` items (`is_embedded=False`)."""
        stmt = (
            select(DocumentChunk)
            .where(
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.document_version_id == document_version_id,
                DocumentChunk.is_deleted.is_(False),
                DocumentChunk.is_embedded.is_(False),
            )
            .order_by(DocumentChunk.chunk_index.asc())
            .limit(batch_size)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def filter_existing_content_hashes(
        self,
        hashes: list[str],
        tenant_id: str,
        provider: str,
        model_name: str,
    ) -> set[str]:
        """Idempotency check: Return the subset of `hashes` that already exist in `chunk_embeddings`."""
        if not hashes:
            return set()

        stmt = select(ChunkEmbedding.content_hash).where(
            ChunkEmbedding.tenant_id == tenant_id,
            ChunkEmbedding.content_hash.in_(hashes),
            ChunkEmbedding.provider == provider,
            ChunkEmbedding.model_name == model_name,
            ChunkEmbedding.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def get_existing_embeddings_by_hashes(
        self,
        hashes: list[str],
        tenant_id: str,
        provider: str,
        model_name: str,
    ) -> dict[str, ChunkEmbedding]:
        """Return existing `ChunkEmbedding` records mapped by `content_hash`."""
        if not hashes:
            return {}

        stmt = select(ChunkEmbedding).where(
            ChunkEmbedding.tenant_id == tenant_id,
            ChunkEmbedding.content_hash.in_(hashes),
            ChunkEmbedding.provider == provider,
            ChunkEmbedding.model_name == model_name,
            ChunkEmbedding.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        records = result.scalars().all()
        return {rec.content_hash: rec for rec in records}

    async def bulk_insert_chunk_embeddings(self, records: list[ChunkEmbedding]) -> int:
        """Bulk insert `ChunkEmbedding` records into staging storage (`chunk_embeddings`)."""
        if not records:
            return 0
        self.session.add_all(records)
        await self.session.flush()
        return len(records)

    async def mark_chunks_as_embedded(
        self, chunk_ids: list[uuid.UUID], tenant_id: str
    ) -> int:
        """Update `DocumentChunk.is_embedded = True` for successfully vectorized chunks."""
        if not chunk_ids:
            return 0
        stmt = (
            update(DocumentChunk)
            .where(
                DocumentChunk.id.in_(chunk_ids),
                DocumentChunk.tenant_id == tenant_id,
            )
            .values(is_embedded=True)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def get_tenant_metrics(self, tenant_id: str) -> dict[str, Any]:
        """Aggregate tenant-level vector counts, token consumption, and job status counters."""
        active_stmt = (
            select(func.count())
            .select_from(EmbeddingJob)
            .where(
                EmbeddingJob.tenant_id == tenant_id,
                EmbeddingJob.status.in_(["PENDING", "PROCESSING"]),
                EmbeddingJob.is_deleted.is_(False),
            )
        )
        active_count = (await self.session.execute(active_stmt)).scalar() or 0

        completed_stmt = (
            select(func.count())
            .select_from(EmbeddingJob)
            .where(
                EmbeddingJob.tenant_id == tenant_id,
                EmbeddingJob.status == "COMPLETED",
                EmbeddingJob.is_deleted.is_(False),
            )
        )
        completed_count = (await self.session.execute(completed_stmt)).scalar() or 0

        failed_stmt = (
            select(func.count())
            .select_from(EmbeddingJob)
            .where(
                EmbeddingJob.tenant_id == tenant_id,
                EmbeddingJob.status == "FAILED",
                EmbeddingJob.is_deleted.is_(False),
            )
        )
        failed_count = (await self.session.execute(failed_stmt)).scalar() or 0

        tokens_stmt = (
            select(func.coalesce(func.sum(EmbeddingJob.total_tokens_consumed), 0))
            .select_from(EmbeddingJob)
            .where(
                EmbeddingJob.tenant_id == tenant_id,
                EmbeddingJob.is_deleted.is_(False),
            )
        )
        total_tokens = (await self.session.execute(tokens_stmt)).scalar() or 0

        vectors_stmt = (
            select(func.count())
            .select_from(ChunkEmbedding)
            .where(
                ChunkEmbedding.tenant_id == tenant_id,
                ChunkEmbedding.is_deleted.is_(False),
            )
        )
        total_vectors = (await self.session.execute(vectors_stmt)).scalar() or 0

        dist_stmt = (
            select(ChunkEmbedding.provider, func.count())
            .where(
                ChunkEmbedding.tenant_id == tenant_id,
                ChunkEmbedding.is_deleted.is_(False),
            )
            .group_by(ChunkEmbedding.provider)
        )
        dist_res = await self.session.execute(dist_stmt)
        provider_distribution = {row[0]: row[1] for row in dist_res.all()}

        return {
            "tenant_id": tenant_id,
            "monthly_token_quota": 1000000,
            "remaining_tokens": 1000000 - total_tokens,
            "active_jobs_count": active_count,
            "completed_jobs_count": completed_count,
            "failed_jobs_count": failed_count,
            "total_tokens_consumed": total_tokens,
            "total_vectors_stored": total_vectors,
            "provider_distribution": provider_distribution,
        }
