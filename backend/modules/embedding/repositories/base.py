"""Embedding Repository Abstract Interface (`IEmbeddingRepository`).

Defines the contractual persistence interface for managing batch jobs (`EmbeddingJob`),
vector staging (`ChunkEmbedding`), idempotency hash queries (`filter_existing_content_hashes`),
and tenant quota/metrics aggregation across multi-tenant boundaries (`ADR-005`).
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any
import uuid

from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.embedding.models.embedding_job import EmbeddingJob


class IEmbeddingRepository(ABC):
    """Abstract interface for embedding domain persistence operations."""

    @abstractmethod
    async def create_job(self, job: EmbeddingJob) -> EmbeddingJob:
        """Persist a new `EmbeddingJob` in the database."""
        pass

    @abstractmethod
    async def get_job_by_id_and_tenant(
        self, job_id: uuid.UUID, tenant_id: str
    ) -> EmbeddingJob | None:
        """Fetch an `EmbeddingJob` by UUID ensuring tenant boundary isolation."""
        pass

    @abstractmethod
    async def list_jobs_by_tenant(
        self,
        tenant_id: str,
        document_id: uuid.UUID | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[EmbeddingJob], int]:
        """Fetch paginated `EmbeddingJob` records and total matching count for a tenant."""
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def get_unembedded_chunks(
        self,
        tenant_id: str,
        document_version_id: uuid.UUID,
        batch_size: int = 100,
    ) -> Sequence[Any]:
        """Fetch up to `batch_size` unindexed `DocumentChunk` items (`is_embedded=False`)."""
        pass

    @abstractmethod
    async def filter_existing_content_hashes(
        self,
        hashes: list[str],
        tenant_id: str,
        provider: str,
        model_name: str,
    ) -> set[str]:
        """Idempotency check: Return the subset of `hashes` that already exist in `chunk_embeddings`."""
        pass

    @abstractmethod
    async def get_existing_embeddings_by_hashes(
        self,
        hashes: list[str],
        tenant_id: str,
        provider: str,
        model_name: str,
    ) -> dict[str, ChunkEmbedding]:
        """Return existing `ChunkEmbedding` records mapped by `content_hash`."""
        pass

    @abstractmethod
    async def bulk_insert_chunk_embeddings(self, records: list[ChunkEmbedding]) -> int:
        """Bulk insert `ChunkEmbedding` records into staging storage (`chunk_embeddings`)."""
        pass

    @abstractmethod
    async def mark_chunks_as_embedded(
        self, chunk_ids: list[uuid.UUID], tenant_id: str
    ) -> int:
        """Update `DocumentChunk.is_embedded = True` for successfully vectorized chunks."""
        pass

    @abstractmethod
    async def get_tenant_metrics(self, tenant_id: str) -> dict[str, Any]:
        """Aggregate tenant-level vector counts, token consumption, and job status counters."""
        pass
