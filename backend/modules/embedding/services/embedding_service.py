"""Embedding Service Layer (`EmbeddingService`).

Orchestrates asynchronous vectorization, tenant quota verification, batch segmentation,
idempotency filtering, and versioned domain event publishing (`ADR-M2-001`, `ADR-M2-003`).
"""

from collections.abc import Sequence
from typing import Any
import uuid

import structlog

from backend.cache.locks import LockAcquisitionError, acquire_lock
from backend.core.events.dispatcher import EventDispatcher
from backend.core.events.types import EventType
from backend.modules.embedding.events.payloads import (
    EVENT_EMBEDDING_COMPLETED,
    EVENT_EMBEDDING_FAILED,
    EVENT_EMBEDDING_PROGRESS,
    EVENT_EMBEDDING_STARTED,
    EmbeddingDomainEvent,
    create_embedding_event,
)
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.embedding.models.embedding_job import EmbeddingJob
from backend.modules.embedding.providers.manager import EmbeddingManager
from backend.modules.embedding.repositories.base import IEmbeddingRepository
from backend.modules.embedding.schemas.errors import InvalidInputError, TokenQuotaExceededError

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
            ws_uuid = None
            try:
                ws_uuid = uuid.UUID(tenant_id)
            except Exception:
                pass
            if ws_uuid:
                try:
                    from backend.modules.analytics.services.quota import QuotaGovernor
                    used_tokens = await QuotaGovernor().get_durable_usage(
                        ws_uuid, session=self.repository.session
                    )
                except Exception:
                    pass
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

            cached_chunks: list[DocumentChunk] = []
            cached_embeddings_to_insert: list[ChunkEmbedding] = []
            missing_chunks: list[DocumentChunk] = []

            if not force_reembed:
                hashes = [c.content_hash for c in chunks]
                cached_map = await self.repository.get_existing_embeddings_by_hashes(
                    hashes, tenant_id, job.provider, job.model_name
                )
                for chunk in chunks:
                    cached_rec = cached_map.get(chunk.content_hash)
                    if (
                        cached_rec is not None
                        and cached_rec.dimension == manager.dimension
                        and isinstance(cached_rec.embedding_vector, list)
                        and len(cached_rec.embedding_vector) == manager.dimension
                    ):
                        cached_chunks.append(chunk)
                        cached_embeddings_to_insert.append(
                            ChunkEmbedding(
                                tenant_id=tenant_id,
                                chunk_id=chunk.id,
                                document_version_id=job.document_version_id,
                                content_hash=chunk.content_hash,
                                provider=job.provider,
                                model_name=job.model_name,
                                dimension=manager.dimension,
                                embedding_vector=cached_rec.embedding_vector,
                            )
                        )
                    else:
                        missing_chunks.append(chunk)
            else:
                missing_chunks = list(chunks)

            # Milestone 5 (AUD-010): Distributed chunk embedding lock with Redis outage fallback
            chunks_to_vectorize = []
            acquired_locks = []

            for chunk in missing_chunks:
                lock_name = f"embed:{tenant_id}:{chunk.content_hash}"
                try:
                    lock_ctx = acquire_lock(lock_name, timeout=30, acquire_timeout=10)
                    token = await lock_ctx.__aenter__()
                    acquired_locks.append(lock_ctx)

                    # Re-check cache under lock in case another worker vectorized it while waiting
                    recheck_map = await self.repository.get_existing_embeddings_by_hashes(
                        [chunk.content_hash], tenant_id, job.provider, job.model_name
                    )
                    cached_rec = recheck_map.get(chunk.content_hash)
                    if (
                        cached_rec is not None
                        and cached_rec.dimension == manager.dimension
                        and isinstance(cached_rec.embedding_vector, list)
                        and len(cached_rec.embedding_vector) == manager.dimension
                    ):
                        cached_chunks.append(chunk)
                        cached_embeddings_to_insert.append(
                            ChunkEmbedding(
                                tenant_id=tenant_id,
                                chunk_id=chunk.id,
                                document_version_id=job.document_version_id,
                                content_hash=chunk.content_hash,
                                provider=job.provider,
                                model_name=job.model_name,
                                dimension=manager.dimension,
                                embedding_vector=cached_rec.embedding_vector,
                            )
                        )
                    else:
                        chunks_to_vectorize.append(chunk)
                except LockAcquisitionError:
                    # Acquisition timed out (10s) — re-check cache to see if prior holder completed
                    recheck_map = await self.repository.get_existing_embeddings_by_hashes(
                        [chunk.content_hash], tenant_id, job.provider, job.model_name
                    )
                    cached_rec = recheck_map.get(chunk.content_hash)
                    if (
                        cached_rec is not None
                        and cached_rec.dimension == manager.dimension
                        and isinstance(cached_rec.embedding_vector, list)
                        and len(cached_rec.embedding_vector) == manager.dimension
                    ):
                        cached_chunks.append(chunk)
                        cached_embeddings_to_insert.append(
                            ChunkEmbedding(
                                tenant_id=tenant_id,
                                chunk_id=chunk.id,
                                document_version_id=job.document_version_id,
                                content_hash=chunk.content_hash,
                                provider=job.provider,
                                model_name=job.model_name,
                                dimension=manager.dimension,
                                embedding_vector=cached_rec.embedding_vector,
                            )
                        )
                    else:
                        # Proceed with vectorization as fallback (at-least-once guarantee)
                        chunks_to_vectorize.append(chunk)
                except Exception as redis_err:
                    # Redis outage fallback: log warning and proceed without distributed locking.
                    # Database integrity is enforced by schema unique constraints.
                    logger.warning(
                        "Redis distributed lock unavailable during embedding; falling back to optimistic DB execution",
                        chunk_hash=chunk.content_hash,
                        tenant_id=tenant_id,
                        error=str(redis_err),
                    )
                    chunks_to_vectorize.append(chunk)

            # Fast-path for already vectorized chunks (Zero-call idempotency check)
            if cached_chunks:
                await self.repository.bulk_insert_chunk_embeddings(
                    cached_embeddings_to_insert
                )
                await self.repository.mark_chunks_as_embedded(
                    [c.id for c in cached_chunks], tenant_id
                )
                await self.repository.update_job_progress(
                    job_id, tenant_id, processed_delta=len(cached_chunks)
                )

            # Vectorize missing chunks via external or local provider
            try:
                if chunks_to_vectorize:
                    texts = [c.content for c in chunks_to_vectorize]
                    try:
                        from backend.cache.rate_limit import RateLimiter, RateLimitExceeded
                        from backend.modules.embedding.schemas.errors import RateLimitExceededError

                        try:
                            await RateLimiter.check_limit(
                                tenant=tenant_id, domain="embeddings", action="api", entity_id="global", limit=600, window_seconds=60
                            )
                        except RateLimitExceeded:
                            raise RateLimitExceededError("Rate limit exceeded for provider API")

                        # Quota pre-check (GAP-QTA-02 / GAP-QTA-04)
                        ws_uuid = None
                        try:
                            ws_uuid = uuid.UUID(tenant_id)
                        except Exception:
                            pass
                        governor = None
                        if ws_uuid:
                            from backend.modules.analytics.services.quota import QuotaGovernor
                            from backend.modules.embedding.schemas.errors import TokenQuotaExceededError
                            governor = QuotaGovernor()

                            # Calculate defensible batch token estimate before calling provider (~1 token per 4 chars)
                            est_batch_tokens = max(1, sum(max(1, len(str(t or "")) // 4) for t in texts))

                            is_exceeded, used, limit, is_hard = await governor.check_quota(
                                workspace_id=ws_uuid,
                                tenant_id=tenant_id,
                                session=self.repository.session,
                            )
                            if is_hard and (used + est_batch_tokens > limit):
                                logger.error(
                                    "Workspace token budget exhausted during embedding batch (EMB_002)",
                                    workspace_id=str(ws_uuid),
                                    used=used,
                                    estimated_batch=est_batch_tokens,
                                    limit=limit,
                                )
                                raise TokenQuotaExceededError(
                                    f"Workspace '{ws_uuid}' token quota exceeded: estimated batch {est_batch_tokens} tokens exceeds remaining balance ({used}/{limit}).",
                                    detail={"used": used, "estimated_batch": est_batch_tokens, "limit": limit, "workspace_id": str(ws_uuid)},
                                )

                        result = await manager.vectorize_batch(texts, batch_size=batch_size)

                        provider_used = result.provider_metadata.get("fallback_provider", job.provider) if isinstance(result.provider_metadata, dict) else job.provider
                        from backend.modules.analytics.services.pricing import ModelPricingService
                        pricing_service = ModelPricingService()
                        cost_res = pricing_service.calculate_cost(
                            provider=provider_used,
                            model_name=job.model_name,
                            prompt_tokens=result.tokens_consumed,
                            completion_tokens=0,
                        )
                        cost = cost_res.total_cost_usd

                        step_metrics = {"estimated_cost_usd": cost}
                        fallback_prov = provider_used if provider_used != job.provider else None
                    except Exception as exc:
                        await self.repository.update_job_progress(
                            job_id,
                            tenant_id,
                            failed_delta=len(chunks_to_vectorize),
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
                        import traceback
                        logger.error(
                            "embedding_batch_failed", job_id=job_id, error=str(exc), traceback=traceback.format_exc()
                        )
                        raise

                    new_recs = []
                    for idx, chunk in enumerate(chunks_to_vectorize):
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
                        [c.id for c in chunks_to_vectorize], tenant_id
                    )
                    await self.repository.update_job_progress(
                        job_id,
                        tenant_id,
                        processed_delta=len(chunks_to_vectorize),
                        tokens_delta=result.tokens_consumed,
                        step_metrics_update=step_metrics,
                        fallback_provider=fallback_prov,
                    )

                    # Deduct tokens from workspace usage atomically with idempotent correlation ID (GAP-QTA-02)
                    if result.tokens_consumed > 0 and ws_uuid:
                        emb_corr_id = f"emb:{job_id}:{job.document_version_id}:{new_recs[0].chunk_id}"
                        try:
                            if governor is None:
                                from backend.modules.analytics.services.quota import QuotaGovernor
                                governor = QuotaGovernor()
                            await governor.record_token_usage(
                                workspace_id=ws_uuid,
                                tenant_id=tenant_id,
                                prompt_tokens=result.tokens_consumed,
                                completion_tokens=0,
                                correlation_id=emb_corr_id,
                                provider=provider_used,
                                model_name=job.model_name,
                                total_cost_usd=cost,
                                session=self.repository.session,
                            )
                        except Exception as q_rec_err:
                            logger.warning("Failed recording embedding token usage", error=str(q_rec_err))
            finally:
                for lock_ctx in acquired_locks:
                    try:
                        await lock_ctx.__aexit__(None, None, None)
                    except Exception as rel_err:
                        logger.warning("Failed to release chunk embedding lock", error=str(rel_err))

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
