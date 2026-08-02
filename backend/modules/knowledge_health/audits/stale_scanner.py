"""Stale Embedding Scanner (`StaleEmbeddingScanner`).

Identifies embedding model drift when a tenant rotates model providers or versions,
and orchestrates shadow re-indexing (`ADR-M6-002`).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.core.events.dispatcher import EventDispatcher, get_dispatcher
from backend.core.events.types import EventType
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.knowledge_health.events.payloads import (
    KnowledgeDriftDetectedPayload,
    KnowledgeHealthDomainEvent,
)
from backend.modules.knowledge_health.models.stale_record import StaleEmbeddingRecord
from backend.modules.knowledge_health.repositories.health_repository import HealthRepository

logger = structlog.get_logger(__name__)


class StaleEmbeddingScanner:
    """Scans for model configuration drift and manages shadow re-indexing campaigns."""

    def __init__(
        self,
        session: AsyncSession,
        repository: HealthRepository | None = None,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self.session = session
        self.repo = repository or HealthRepository(session)
        self.dispatcher = dispatcher or get_dispatcher()

    async def detect_stale_embeddings(
        self,
        tenant_id: str,
        active_provider: str,
        active_model: str,
    ) -> list[StaleEmbeddingRecord]:
        """Find chunk embeddings created with older or differing models than the active tenant configuration."""
        log = logger.bind(
            tenant_id=tenant_id,
            active_provider=active_provider,
            active_model=active_model,
        )
        log.info("Scanning for stale chunk embeddings")

        stmt = select(ChunkEmbedding).where(
            ChunkEmbedding.tenant_id == tenant_id,
            ChunkEmbedding.is_deleted.is_(False),
            (ChunkEmbedding.provider != active_provider)
            | (ChunkEmbedding.model_name != active_model),
        )
        stale_embs = (await self.session.execute(stmt)).scalars().all()

        if not stale_embs:
            log.info("Zero stale chunk embeddings found")
            return []

        # Check existing pending records to avoid duplicates
        existing_records = await self.repo.get_stale_records(
            tenant_id=tenant_id, status="PENDING"
        )
        existing_chunk_ids = {r.chunk_id for r in existing_records}

        new_records: list[StaleEmbeddingRecord] = []
        for emb in stale_embs:
            if emb.chunk_id not in existing_chunk_ids:
                rec = StaleEmbeddingRecord(
                    tenant_id=tenant_id,
                    chunk_id=emb.chunk_id,
                    old_provider=emb.provider,
                    old_model_name=emb.model_name,
                    target_provider=active_provider,
                    target_model_name=active_model,
                    status="PENDING",
                )
                await self.repo.create_stale_record(rec)
                new_records.append(rec)
                existing_chunk_ids.add(emb.chunk_id)

        await self.session.flush()

        all_pending = existing_records + new_records
        if new_records:
            log.warning(
                "Identified new stale embeddings requiring re-index",
                count=len(new_records),
                total_pending=len(all_pending),
            )
            payload = KnowledgeDriftDetectedPayload(
                tenant_id=tenant_id,
                drift_type="MODEL_ROTATION_STALE",
                details={
                    "stale_chunks_found": len(all_pending),
                    "target_provider": active_provider,
                    "target_model": active_model,
                },
            )
            await self.dispatcher.publish(
                KnowledgeHealthDomainEvent(
                    event_type=EventType.KNOWLEDGE_DRIFT_DETECTED,
                    payload=payload.to_dict(),
                )
            )

        return all_pending

    async def trigger_shadow_reindex(
        self,
        tenant_id: str,
        records: list[StaleEmbeddingRecord],
        target_provider: str,
        target_model: str,
    ) -> uuid.UUID:
        """Create migration job ID and enqueue records for batch re-embedding."""
        job_id = uuid.uuid4()
        log = logger.bind(tenant_id=tenant_id, job_id=str(job_id), count=len(records))
        log.info("Triggering shadow re-index campaign for stale embedding records")

        for rec in records:
            await self.repo.update_stale_record_status(rec.id, status="PROCESSING")

        await self.session.flush()
        return job_id
