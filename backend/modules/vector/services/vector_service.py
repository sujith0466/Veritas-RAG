"""Vector Storage Foundation Service (`VectorStorageService`).

Orchestrates multi-tenant collection creation, exact payload index setup (`ADR-M3-001`),
batch point upserts into Qdrant (`ADR-004`), synchronization state tracking inside
PostgreSQL (`VectorIndexMetadata`), and domain event distribution (`VectorsIndexed`).
"""

import asyncio
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.cache.locks import LockAcquisitionError, acquire_lock

from backend.core.config import get_settings
from backend.core.events.dispatcher import EventDispatcher, get_dispatcher
from backend.core.events.types import EventType
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.vector.events.payloads import (
    VectorDomainEvent,
    create_vector_index_failed_payload,
    create_vector_indexed_payload,
)
from backend.modules.vector.models.vector_metadata import VectorIndexMetadata
from backend.modules.vector.providers.base import BaseVectorDBProvider
from backend.modules.vector.providers.factory import VectorProviderFactory
from backend.modules.vector.repositories.vector_repository import VectorMetadataRepository
from backend.modules.vector.schemas.payload import (
    CollectionConfigDTO,
    CollectionSummaryDTO,
    VectorPointDTO,
)

logger = structlog.get_logger(__name__)

RESERVED_PAYLOAD_FIELDS: frozenset[str] = frozenset({
    "tenant_id",
    "document_id",
    "document_version_id",
    "content_hash",
    "content",
    "strategy_used",
    "chunk_index",
    "token_count",
    "character_count",
    "section_path",
    "page_numbers",
    "provider",
    "model_name",
    "source_type",
    "source_url",
    "canonical_url",
    "final_url",
    "title",
})


class VectorStorageService:
    """Domain service orchestrating vector storage operations (`ADR-004`, `ADR-M3-001`)."""

    def __init__(
        self,
        session: AsyncSession,
        provider: BaseVectorDBProvider | None = None,
        dispatcher: EventDispatcher | None = None,
    ) -> None:
        self.session = session
        self.provider = provider or VectorProviderFactory.get_provider("qdrant")
        self.dispatcher = dispatcher or get_dispatcher()
        self.repo = VectorMetadataRepository(session)

    async def sync_document_vectors(
        self,
        document_id: str | uuid.UUID,
        document_version_id: str | uuid.UUID,
        tenant_id: str,
        collection_name: str | None = None,
    ) -> int:
        """Fetch staged chunk embeddings and sync them as indexed points into Qdrant."""
        doc_uuid = (
            document_id
            if isinstance(document_id, uuid.UUID)
            else uuid.UUID(str(document_id))
        )
        ver_uuid = (
            document_version_id
            if isinstance(document_version_id, uuid.UUID)
            else uuid.UUID(str(document_version_id))
        )

        log = logger.bind(
            tenant_id=tenant_id,
            document_id=str(doc_uuid),
            document_version_id=str(ver_uuid),
        )
        log.info("Starting document vector synchronization to Qdrant")

        # 1. Fetch staged embeddings for this document version
        emb_stmt = select(ChunkEmbedding).where(
            ChunkEmbedding.tenant_id == tenant_id,
            ChunkEmbedding.document_version_id == ver_uuid,
            ChunkEmbedding.is_deleted.is_(False),
        )
        embeddings = (await self.session.execute(emb_stmt)).scalars().all()
        if not embeddings:
            log.warning(
                "No staged chunk embeddings found for document version; skipping sync"
            )
            return 0

        # 2. Fetch corresponding document chunks for rich payload metadata
        chunk_stmt = select(DocumentChunk).where(
            DocumentChunk.tenant_id == tenant_id,
            DocumentChunk.document_version_id == ver_uuid,
            DocumentChunk.is_deleted.is_(False),
        )
        chunks = (await self.session.execute(chunk_stmt)).scalars().all()
        chunks_map = {str(c.id): c for c in chunks}
        # Also index by uuid directly just in case
        for c in chunks:
            chunks_map[c.id] = c

        # 3. Determine target collection topology and create/update metadata state
        first_emb = embeddings[0]
        dimension = first_emb.dimension
        settings = get_settings()
        target_col = collection_name or settings.qdrant.collection_name(tenant_id)

        metadata_record = await self.repo.get_or_create_metadata(
            tenant_id=tenant_id,
            document_id=doc_uuid,
            document_version_id=ver_uuid,
            collection_name=target_col,
        )
        await self.repo.update_sync_status(metadata_record.id, status="PROCESSING")

        # Fetch document to attach user_metadata and website provenance
        from backend.document.repositories.document_repository import DocumentRepository
        doc_repo = DocumentRepository()
        doc = await doc_repo.get_by_id(doc_uuid, tenant_id, self.session)
        doc_user_meta = getattr(doc, "user_metadata", {}) or {}
        raw_user_meta = dict(doc_user_meta) if isinstance(doc_user_meta, dict) else {}
        clean_user_meta = {
            k: v for k, v in raw_user_meta.items()
            if k not in RESERVED_PAYLOAD_FIELDS
        }

        raw_source_type = getattr(doc, "source_type", None) or "file_upload"
        doc_source_type = (
            raw_source_type.value
            if hasattr(raw_source_type, "value")
            else str(raw_source_type)
        )
        doc_source_url = getattr(doc, "source_url", None)
        doc_canonical_url = getattr(doc, "canonical_url", None)
        doc_final_url = getattr(doc, "final_url", None)
        doc_title = getattr(doc, "filename", None)

        try:
            # 4. Ensure collection exists with exact HNSW & INT8 scalar quantization (`ADR-M3-002`)
            col_config = CollectionConfigDTO(
                collection_name=target_col,
                dimension=dimension,
                distance_metric="Cosine",
                on_disk_payload=True,
                scalar_quantization=True,
            )
            await self.provider.ensure_collection(col_config)

            # 5. Create payload indices for instantaneous multi-tenant filtering (`ADR-M3-001`)
            await self.provider.create_payload_indexes(
                collection_name=target_col,
                indexed_fields=[
                    "tenant_id",
                    "document_id",
                    "document_version_id",
                    "content_hash",
                    "strategy_used",
                    "source_type",
                ],
            )

            # 6. Build point DTOs
            points: list[VectorPointDTO] = []
            for emb in embeddings:
                chunk = chunks_map.get(emb.chunk_id) or chunks_map.get(
                    str(emb.chunk_id)
                )
                payload: dict[str, Any] = {
                    **clean_user_meta,  # Inject dynamic metadata tags (sanitized)
                    "tenant_id": tenant_id,
                    "document_id": str(doc_uuid),
                    "document_version_id": str(ver_uuid),
                    "content_hash": emb.content_hash,
                    "content": getattr(chunk, "content", "") if chunk else "",
                    "strategy_used": (
                        getattr(chunk, "strategy_used", "hierarchical")
                        if chunk
                        else "hierarchical"
                    ),
                    "chunk_index": getattr(chunk, "chunk_index", 0) if chunk else 0,
                    "token_count": getattr(chunk, "token_count", 0) if chunk else 0,
                    "character_count": (
                        getattr(chunk, "character_count", 0) if chunk else 0
                    ),
                    "section_path": (
                        getattr(chunk, "section_path", None) if chunk else None
                    ),
                    "page_numbers": (
                        getattr(chunk, "page_numbers", None) if chunk else None
                    ),
                    "provider": emb.provider,
                    "model_name": emb.model_name,
                    "source_type": doc_source_type,
                    "source_url": doc_source_url,
                    "canonical_url": doc_canonical_url,
                    "final_url": doc_final_url,
                    "title": doc_title,
                }

                points.append(
                    VectorPointDTO(
                        point_id=str(emb.chunk_id),
                        vector=emb.embedding_vector,
                        payload=payload,
                    )
                )

            # 7. Batch upsert points into Qdrant
            VECTOR_UPSERT_BATCH_SIZE = 500
            upserted_count = 0
            for i in range(0, len(points), VECTOR_UPSERT_BATCH_SIZE):
                batch = points[i : i + VECTOR_UPSERT_BATCH_SIZE]
                count = await self.provider.upsert_points(target_col, batch)
                upserted_count += count

            log.info(
                "Successfully upserted points to Qdrant", upserted_count=upserted_count
            )

            # 8. Mark metadata completed and emit versioned domain event
            await self.repo.update_sync_status(
                metadata_record.id,
                status="COMPLETED",
                points_count=upserted_count,
            )
            await self.session.commit()

            payload_event = create_vector_indexed_payload(
                tenant_id=tenant_id,
                document_id=doc_uuid,
                document_version_id=ver_uuid,
                collection_name=target_col,
                points_count=upserted_count,
                dimension=dimension,
            )
            await self.dispatcher.publish(
                VectorDomainEvent(
                    event_type=EventType.VECTORS_INDEXED, payload=payload_event
                )
            )

            return upserted_count

        except Exception as exc:
            err_code = getattr(exc, "code", "VEC_003")
            err_msg = str(exc)
            log.error(
                "Document vector synchronization failed",
                error_code=err_code,
                error=err_msg,
            )

            await self.repo.update_sync_status(
                metadata_record.id,
                status="FAILED",
                error_message=err_msg,
            )
            await self.session.commit()

            fail_event = create_vector_index_failed_payload(
                tenant_id=tenant_id,
                document_id=doc_uuid,
                document_version_id=ver_uuid,
                collection_name=target_col,
                error_code=str(err_code),
                error_message=err_msg,
            )
            await self.dispatcher.publish(
                VectorDomainEvent(
                    event_type=EventType.VECTORS_INDEX_FAILED, payload=fail_event
                )
            )
            raise

    async def remove_archived_document_vectors(
        self,
        document_id: str | uuid.UUID,
        tenant_id: str,
        collection_name: str | None = None,
    ) -> int:
        """Purge all vectors for a document when it is archived (F5.5)."""
        return await self.delete_document_points(document_id, tenant_id, collection_name)

    async def delete_document_points(
        self,
        document_id: str | uuid.UUID,
        tenant_id: str,
        collection_name: str | None = None,
    ) -> int:
        """Purge all vector points associated with a document via exact payload filtering (`ADR-M3-001`)."""
        doc_uuid = (
            document_id
            if isinstance(document_id, uuid.UUID)
            else uuid.UUID(str(document_id))
        )
        log = logger.bind(tenant_id=tenant_id, document_id=str(doc_uuid))

        filter_conds = {
            "tenant_id": tenant_id,
            "document_id": str(doc_uuid),
        }

        if collection_name:
            col_list = [collection_name]
        else:
            # Discover target collections where this document was indexed
            stmt = (
                select(VectorIndexMetadata.collection_name)
                .where(
                    VectorIndexMetadata.tenant_id == tenant_id,
                    VectorIndexMetadata.document_id == doc_uuid,
                    VectorIndexMetadata.is_deleted.is_(False),
                )
                .distinct()
            )
            cols = (await self.session.execute(stmt)).scalars().all()
            col_list = list(cols) if cols else [get_settings().qdrant.collection_name(tenant_id)]

        total_ops = 0
        for col in col_list:
            try:
                op_id = await self.provider.delete_points_by_filter(col, filter_conds)
                total_ops += op_id
            except Exception as exc:
                err_str = str(exc).lower()
                if "not found" in err_str:
                    log.info(
                        "Target collection not found during point deletion; vectors already absent",
                        collection=col,
                    )
                else:
                    log.error(
                        "Failed to delete points from collection during purge",
                        collection=col,
                        error=str(exc),
                    )
                    raise

        # Soft delete metadata records
        meta_stmt = select(VectorIndexMetadata).where(
            VectorIndexMetadata.tenant_id == tenant_id,
            VectorIndexMetadata.document_id == doc_uuid,
            VectorIndexMetadata.is_deleted.is_(False),
        )
        meta_records = (await self.session.execute(meta_stmt)).scalars().all()
        for rec in meta_records:
            await self.repo.update_sync_status(
                rec.id, status="FAILED", error_message="Document deleted"
            )
            rec.is_deleted = True

        await self.session.flush()
        log.info(
            "Completed document point deletion across collections", collections=col_list
        )
        return total_ops

    async def cleanup_old_versions_vectors(
        self,
        document_id: str | uuid.UUID,
        current_version_id: str | uuid.UUID,
        tenant_id: str,
        collection_name: str | None = None,
    ) -> int:
        """Purge vector points for older versions of a document after a new version is indexed (F5.6)."""
        doc_uuid = (
            document_id
            if isinstance(document_id, uuid.UUID)
            else uuid.UUID(str(document_id))
        )
        ver_uuid = (
            current_version_id
            if isinstance(current_version_id, uuid.UUID)
            else uuid.UUID(str(current_version_id))
        )
        log = logger.bind(tenant_id=tenant_id, document_id=str(doc_uuid), keeping_version=str(ver_uuid))

        meta_stmt = select(VectorIndexMetadata).where(
            VectorIndexMetadata.tenant_id == tenant_id,
            VectorIndexMetadata.document_id == doc_uuid,
            VectorIndexMetadata.document_version_id != ver_uuid,
            VectorIndexMetadata.is_deleted.is_(False),
        )
        meta_records = (await self.session.execute(meta_stmt)).scalars().all()

        if not meta_records:
            return 0

        total_ops = 0
        for rec in meta_records:
            col = rec.collection_name
            filter_conds = {
                "tenant_id": tenant_id,
                "document_version_id": str(rec.document_version_id),
            }
            deleted_successfully = False
            for attempt in range(1, 4):
                try:
                    op_id = await self.provider.delete_points_by_filter(col, filter_conds)
                    total_ops += op_id
                    await self.repo.update_sync_status(
                        rec.id, status="FAILED", error_message="Superseded by newer version"
                    )
                    rec.is_deleted = True
                    deleted_successfully = True
                    break
                except Exception as exc:
                    if attempt < 3:
                        await asyncio.sleep(0.2 * attempt)
                    else:
                        log.warning(
                            "Failed to delete old version points from collection after retries",
                            collection=col,
                            version_id=str(rec.document_version_id),
                            error=str(exc),
                        )
                        # Mark record as CLEANUP_PENDING with error details, keeping is_deleted=False for reconciliation
                        await self.repo.update_sync_status(
                            rec.id, status="CLEANUP_PENDING", error_message=f"Qdrant purge failed: {exc!s}"
                        )
                        rec.is_deleted = False

        await self.session.flush()
        log.info(
            "Completed cleanup of old version vectors", total_deleted_ops=total_ops
        )
        return total_ops

    async def reconcile_superseded_vectors(self, tenant_id: str | None = None) -> int:
        """Periodic or event-triggered idempotent reconciliation of CLEANUP_PENDING vector records."""
        lock_key = f"cleanup:reconciliation:{tenant_id or 'global'}"
        try:
            async with acquire_lock(lock_key, timeout=120, acquire_timeout=2):
                stmt = select(VectorIndexMetadata).where(
                    VectorIndexMetadata.status == "CLEANUP_PENDING",
                    VectorIndexMetadata.is_deleted.is_(False),
                )
                if tenant_id:
                    stmt = stmt.where(VectorIndexMetadata.tenant_id == tenant_id)

                pending_records = (await self.session.execute(stmt)).scalars().all()
                if not pending_records:
                    return 0

                reconciled_ops = 0
                for rec in pending_records:
                    filter_conds = {
                        "tenant_id": rec.tenant_id,
                        "document_version_id": str(rec.document_version_id),
                    }
                    try:
                        op_id = await self.provider.delete_points_by_filter(rec.collection_name, filter_conds)
                        reconciled_ops += op_id
                        await self.repo.update_sync_status(
                            rec.id, status="FAILED", error_message="Superseded by newer version"
                        )
                        rec.is_deleted = True
                    except Exception as exc:
                        logger.warning(
                            "Reconciliation purge retry failed",
                            metadata_id=str(rec.id),
                            tenant_id=rec.tenant_id,
                            error=str(exc),
                        )

                await self.session.flush()
                logger.info("Completed superseded vector reconciliation", reconciled_ops=reconciled_ops)
                return reconciled_ops
        except LockAcquisitionError:
            logger.info("Reconciliation already in progress for lock key; skipping", lock_key=lock_key)
            return 0

    async def sync_metadata(self, doc: Any) -> None:
        """Update Qdrant point payloads with the latest user_metadata from PostgreSQL."""
        log = logger.bind(tenant_id=doc.tenant_id, document_id=str(doc.id))

        # 1. Discover collections this document is indexed in
        stmt = (
            select(VectorIndexMetadata.collection_name)
            .where(
                VectorIndexMetadata.tenant_id == doc.tenant_id,
                VectorIndexMetadata.document_id == doc.id,
                VectorIndexMetadata.is_deleted.is_(False),
            )
            .distinct()
        )
        cols = (await self.session.execute(stmt)).scalars().all()

        if not cols:
            log.warning("No collections found for document metadata sync")
            return

        # 2. Extract new metadata dictionary
        user_meta = dict(getattr(doc, "user_metadata", {}))

        # 3. Update payloads in Qdrant (using filtering by document_id)
        filter_conds = {
            "tenant_id": doc.tenant_id,
            "document_id": str(doc.id),
        }

        # In Qdrant, we can use `set_payload` or just re-upsert. Since we only want to update user_metadata,
        # we can put user_metadata inside the payload. But we don't have a direct `set_payload` in our provider yet.
        # Let's see if we have `update_points_payload` or we can fallback to re-upsert if needed.
        # Wait, the architecture review says: "This task will `upsert` the new metadata payload into Qdrant".
        # We can update the payload via the provider.

        # Since I don't know the exact provider methods, I'll check if `update_payload_by_filter` exists.
        # If not, I can just re-sync the document vectors by calling `sync_document_vectors`.

        if doc.latest_version_id:
            await self.sync_document_vectors(doc.id, doc.latest_version_id, doc.tenant_id)
            log.info("Triggered re-sync of document vectors to apply metadata")
        else:
            log.warning("Document has no latest_version_id; cannot re-sync vectors")

    async def get_tenant_summary(self, tenant_id: str) -> dict[str, Any]:
        """Return aggregate summary metrics for a tenant's vector collections."""
        return await self.repo.get_tenant_collection_summary(tenant_id)

    async def get_collection_status(self, collection_name: str) -> CollectionSummaryDTO:
        """Fetch live Qdrant cluster health summary for a specific collection."""
        return await self.provider.get_collection_info(collection_name)
