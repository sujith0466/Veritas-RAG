from backend.document.models.status import DocumentStatus
"""Embedding Service Layer (`EmbeddingService`).

Orchestrates asynchronous vectorization, tenant quota verification, batch segmentation,
idempotency filtering, and versioned domain event publishing (`ADR-M2-001`, `ADR-M2-003`).
"""

import uuid
from collections.abc import Sequence
from typing import Any

import structlog

from backend.core.events.dispatcher import EventDispatcher
from backend.core.events.types import EventType
from backend.modules.embedding.events.payloads import (
    EVENT_EMBEDDING_COMPLETED, EVENT_EMBEDDING_FAILED,
    EVENT_EMBEDDING_PROGRESS, EVENT_EMBEDDING_STARTED, EmbeddingDomainEvent,
    create_embedding_event)
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.embedding.models.embedding_job import EmbeddingJob
from backend.modules.embedding.providers.manager import EmbeddingManager
from backend.modules.embedding.repositories.base import IEmbeddingRepository
from backend.modules.embedding.schemas.errors import (InvalidInputError,
                                                      TokenQuotaExceededError)

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Orchestration service for the Phase 2 Milestone 2 Embedding Pipeline."""

    def __init__(
        self,
        repository: IEmbeddingRepository,
        event_dispatcher: EventDispatcher | None = None,
    ) -> None:
        self.repository = repository
        self.event_dispatcher = event_dispatcher

    async def initiate_embedding_job(
        self,
        tenant_id: str,
        document_id: uuid.UUID,
        document_version_id: uuid.UUID,
        provider: str | None = None,
        model_name: str | None = None,
        force_reembed: bool = False,
        max_token_quota: int | None = None,
    ) -> EmbeddingJob:
        """Verify quota and chunks, create an `EmbeddingJob`, and publish initiation event."""
        # Check available unindexed chunks
        chunks = await self.repository.get_unembedded_chunks(
            tenant_id, document_version_id, batch_size=1000
        )
        if not chunks and not force_reembed:
            raise InvalidInputError(
                "No unindexed chunks found for the specified document version."
            )

        # Enforce multi-tenant token quota (`EMB_002`)
        if max_token_quota is not None:
            metrics = await self.repository.get_tenant_metrics(tenant_id)
            used_tokens = metrics.get("total_tokens_consumed", 0)
            if used_tokens >= max_token_quota:
                raise TokenQuotaExceededError(
                    f"Tenant '{tenant_id}' has exceeded token budget ({used_tokens}/{max_token_quota}).",
                    detail={"used": used_tokens, "quota": max_token_quota},
                )

        manager = EmbeddingManager(provider_name=provider, model_name=model_name)
        resolved_provider = provider or "openai"

        job = EmbeddingJob(
            tenant_id=tenant_id,
            document_id=document_id,
            document_version_id=document_version_id,
            provider=resolved_provider,
            model_name=manager.model_name,
            total_chunks=len(chunks),
            processed_chunks=0,
            failed_chunks=0,
            total_tokens_consumed=0,
            status="PENDING",
        )
        created_job = await self.repository.create_job(job)
        await self.repository.session.commit()

        if self.event_dispatcher:
            payload = create_embedding_event(
                event_type=EVENT_EMBEDDING_STARTED,
                tenant_id=tenant_id,
                document_id=document_id,
                document_version_id=document_version_id,
                job_id=created_job.id,
                data={
                    "provider": resolved_provider,
                    "model": manager.model_name,
                    "total_chunks": len(chunks),
                },
            )
            await self.event_dispatcher.publish(
                EmbeddingDomainEvent(
                    event_type=EventType.EMBEDDING_STARTED, payload=payload
                )
            )

        logger.info(
            "embedding_job_initiated",
            job_id=created_job.id,
            tenant_id=tenant_id,
            provider=resolved_provider,
            chunks=len(chunks),
        )
        return created_job

    async def process_embedding_batch(
        self,
        job_id: uuid.UUID,
        tenant_id: str,
        batch_size: int = 100,
        force_reembed: bool = False,
    ) -> EmbeddingJob:
        """Process unindexed chunks in batches with zero-call idempotency filtering."""
        job = await self.repository.get_job_by_id_and_tenant(job_id, tenant_id)
        if not job:
            raise InvalidInputError(
                f"Embedding job {job_id} not found under tenant {tenant_id}."
            )

        await self.repository.update_job_progress(
            job_id, tenant_id, status="PROCESSING"
        )
        job = (await self.repository.get_job_by_id_and_tenant(job_id, tenant_id)) or job

        manager = EmbeddingManager(
            provider_name=job.provider, model_name=job.model_name
        )

        while True:
            chunks = await self.repository.get_unembedded_chunks(
                tenant_id, job.document_version_id, batch_size=batch_size
            )
            if not chunks:
                break

            if not force_reembed:
                hashes = [c.content_hash for c in chunks]
                existing = await self.repository.filter_existing_content_hashes(
                    hashes, tenant_id, job.provider, job.model_name
                )
                cached_chunks = [c for c in chunks if c.content_hash in existing]
                missing_chunks = [c for c in chunks if c.content_hash not in existing]
            else:
                cached_chunks = []
                missing_chunks = list(chunks)

            # Fast-path for already vectorized chunks (Zero-call idempotency check)
            if cached_chunks:
                await self.repository.mark_chunks_as_embedded(
                    [c.id for c in cached_chunks], tenant_id
                )
                await self.repository.update_job_progress(
                    job_id, tenant_id, processed_delta=len(cached_chunks)
                )

            # Vectorize missing chunks via external or local provider
            if missing_chunks:
                texts = [c.content for c in missing_chunks]
                try:
                    result = await manager.vectorize_batch(texts, batch_size=batch_size)
                except Exception as exc:
                    await self.repository.update_job_progress(
                        job_id,
                        tenant_id,
                        failed_delta=len(missing_chunks),
                        status="FAILED",
                        error_message=str(exc),
                    )
                    if self.event_dispatcher:
                        payload = create_embedding_event(
                            event_type=EVENT_EMBEDDING_FAILED,
                            tenant_id=tenant_id,
                            document_id=job.document_id,
                            document_version_id=job.document_version_id,
                            job_id=job_id,
                            data={"error": str(exc)},
                        )
                        await self.event_dispatcher.publish(
                            EmbeddingDomainEvent(
                                event_type=EventType.EMBEDDING_FAILED, payload=payload
                            )
                        )
                    logger.error(
                        "embedding_batch_failed", job_id=job_id, error=str(exc)
                    )
                    raise

                new_recs = []
                for idx, chunk in enumerate(missing_chunks):
                    new_recs.append(
                        ChunkEmbedding(
                            tenant_id=tenant_id,
                            chunk_id=chunk.id,
                            document_version_id=job.document_version_id,
                            content_hash=chunk.content_hash,
                            provider=job.provider,
                            model_name=job.model_name,
                            dimension=manager.dimension,
                            embedding_vector=result.embeddings[idx],
                        )
                    )

                await self.repository.bulk_insert_chunk_embeddings(new_recs)
                await self.repository.mark_chunks_as_embedded(
                    [c.id for c in missing_chunks], tenant_id
                )
                await self.repository.update_job_progress(
                    job_id,
                    tenant_id,
                    processed_delta=len(missing_chunks),
                    tokens_delta=result.tokens_consumed,
                )

            job = (
                await self.repository.get_job_by_id_and_tenant(job_id, tenant_id)
            ) or job
            if self.event_dispatcher and job:
                payload = create_embedding_event(
                    event_type=EVENT_EMBEDDING_PROGRESS,
                    tenant_id=tenant_id,
                    document_id=job.document_id,
                    document_version_id=job.document_version_id,
                    job_id=job_id,
                    data={
                        "processed": job.processed_chunks,
                        "total": job.total_chunks,
                        "tokens": job.total_tokens_consumed,
                    },
                )
                await self.event_dispatcher.publish(
                    EmbeddingDomainEvent(
                        event_type=EventType.EMBEDDING_PROGRESS, payload=payload
                    )
                )

        completed_job = await self.repository.update_job_progress(
            job_id, tenant_id, status="COMPLETED"
        )
        final_job = completed_job if isinstance(completed_job, EmbeddingJob) else job
        if self.event_dispatcher and final_job:
            payload = create_embedding_event(
                event_type=EVENT_EMBEDDING_COMPLETED,
                tenant_id=tenant_id,
                document_id=final_job.document_id,
                document_version_id=final_job.document_version_id,
                job_id=job_id,
                data={
                    "total_processed": final_job.processed_chunks,
                    "total_tokens": final_job.total_tokens_consumed,
                },
            )
            await self.event_dispatcher.publish(
                EmbeddingDomainEvent(
                    event_type=EventType.EMBEDDING_COMPLETED, payload=payload
                )
            )

        logger.info("embedding_job_completed", job_id=job_id, tenant_id=tenant_id)
        return final_job

    async def get_job_status(
        self, job_id: uuid.UUID, tenant_id: str
    ) -> EmbeddingJob | None:
        """Retrieve `EmbeddingJob` status ensuring multi-tenant namespace check."""
        return await self.repository.get_job_by_id_and_tenant(job_id, tenant_id)

    async def list_jobs(
        self,
        tenant_id: str,
        document_id: uuid.UUID | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[EmbeddingJob], int]:
        """List paginated embedding jobs for a tenant."""
        return await self.repository.list_jobs_by_tenant(
            tenant_id=tenant_id,
            document_id=document_id,
            status=status,
            skip=skip,
            limit=limit,
        )

    async def get_tenant_metrics(self, tenant_id: str) -> dict[str, Any]:
        """Retrieve tenant-level embedding counts, active jobs, and token usage."""
        return await self.repository.get_tenant_metrics(tenant_id)
