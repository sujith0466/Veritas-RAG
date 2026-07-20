"""Chunking Domain Service (`ChunkingService`).

Orchestrates strategy selection, text splitting, quota validation, doubly-linked graph linking,
batch database persistence, contract verification, and event emission (`ADR-005`).
"""

import hashlib
import time
from typing import Sequence
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.models import Document, DocumentEventLog, DocumentVersion
from backend.document.storage import LocalStorageProvider, StorageProvider
from backend.modules.chunking.events import EVENT_DOCUMENT_CHUNKED, create_chunk_event
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.chunking.repositories.chunk_repository import DocumentChunkRepository
from backend.modules.chunking.schemas.chunk import (
    ChunkDetailResponse,
    ChunkListResponse,
    ChunkMetricsDTO,
    ChunkResponse,
    StrategyInfoDTO,
)
from backend.modules.chunking.schemas.errors import (
    ChunkingExecutionError,
    ChunkNotFoundException,
    ChunkValidationError,
)
from backend.modules.chunking.strategies import SplitterStrategyFactory
from backend.modules.chunking.validators import ChunkProcessingContract, ChunkValidator


class ChunkingService:
    """Orchestrates document version splitting and chunk lifecycle."""

    def __init__(
        self,
        storage_provider: StorageProvider | None = None,
        factory: SplitterStrategyFactory | None = None,
        validator: ChunkValidator | None = None,
    ) -> None:
        self.storage = storage_provider or LocalStorageProvider()
        self.factory = factory or SplitterStrategyFactory()
        self.validator = validator or ChunkValidator()

    async def chunk_document_version(
        self,
        tenant_id: str,
        document_id: uuid.UUID,
        version_id: uuid.UUID,
        session: AsyncSession,
        strategy_override: str | None = None,
        max_characters: int = 1000,
        overlap_characters: int = 200,
    ) -> tuple[list[DocumentChunk], float]:
        """Split document version text, persist doubly-linked chunks, verify contract, and emit event (`ADR-005`)."""
        start_time = time.perf_counter()

        # 1. Fetch Document and DocumentVersion entities
        doc_stmt = select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
        doc_result = await session.execute(doc_stmt)
        document = doc_result.scalar_one_or_none()
        if not document:
            raise ChunkNotFoundException(message=f"Document {document_id} not found in tenant namespace.")

        ver_stmt = select(DocumentVersion).where(DocumentVersion.id == version_id, DocumentVersion.document_id == document_id)
        ver_result = await session.execute(ver_stmt)
        version = ver_result.scalar_one_or_none()
        if not version or not version.extracted_text_path:
            raise ChunkNotFoundException(
                message=f"Document version {version_id} or its normalized text artifact is missing (`CHK_005`).",
                detail={"document_id": str(document_id), "version_id": str(version_id)},
            )

        # 2. Retrieve normalized text content from storage provider (`text.txt`)
        if not await self.storage.object_exists(version.extracted_text_path):
            raise ChunkNotFoundException(
                message=f"Physical normalized text object not found at key {version.extracted_text_path}.",
            )
        raw_bytes = await self.storage.get_bytes(version.extracted_text_path)
        normalized_text = raw_bytes.decode("utf-8", errors="replace")

        # 3. Resolve splitting strategy
        mime_type = "text/plain"
        if version.metadata_json and "mime_type" in version.metadata_json:
            mime_type = version.metadata_json["mime_type"]
        elif hasattr(document, "filename") and document.filename.endswith(".md"):
            mime_type = "text/markdown"
        elif hasattr(document, "filename") and document.filename.endswith(".csv"):
            mime_type = "text/csv"

        splitter = self.factory.get_splitter(strategy_name=strategy_override, mime_type=mime_type)
        strategy_code = splitter.strategy_info.name

        # 4. Execute text splitting
        try:
            dtos = splitter.split_text(
                text=normalized_text,
                max_characters=max_characters,
                overlap_characters=overlap_characters,
                base_metadata={"document_id": str(document_id), "version_id": str(version_id)},
            )
        except Exception as exc:
            if hasattr(exc, "error_code"):
                raise exc
            raise ChunkingExecutionError(message=f"Splitting strategy '{strategy_code}' crashed: {exc}") from exc

        # 5. Validate DTO quotas and rules (`CHK_001`)
        self.validator.validate_chunks(dtos)

        # 6. Delete any existing chunks for this version (idempotent re-chunking)
        repo = DocumentChunkRepository(session)
        await repo.delete_chunks_by_version(tenant_id, version_id)

        # 7. Instantiate ORM entities and link doubly-linked sequence pointers (`prev` <-> `next`)
        chunk_entities: list[DocumentChunk] = []
        for idx, dto in enumerate(dtos):
            content_hash = hashlib.sha256(f"{tenant_id}:{document_id}:{version_id}:{idx}:{dto.content}".encode()).hexdigest()
            entity = DocumentChunk(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                document_id=document_id,
                document_version_id=version_id,
                chunk_index=idx,
                content=dto.content,
                content_hash=content_hash,
                strategy_used=strategy_code,
                token_count=dto.token_count,
                character_count=dto.character_count,
                page_numbers=dto.page_numbers or None,
                section_path=dto.section_path or None,
                metadata_json=dto.metadata_json or None,
                is_embedded=False,  # Strictly NO embedding in M1
            )
            chunk_entities.append(entity)

        # Establish doubly-linked foreign key pointers
        for i, entity in enumerate(chunk_entities):
            if i > 0:
                entity.previous_chunk_id = chunk_entities[i - 1].id
            if i < len(chunk_entities) - 1:
                entity.next_chunk_id = chunk_entities[i + 1].id

        # 8. Batch persist chunks to database
        await repo.batch_create_chunks(chunk_entities)

        # 9. Verify processing contract invariants (`CHK_004`)
        ChunkProcessingContract.verify(chunk_entities)

        # 10. Update Document status to CHUNKED and emit domain event
        document.status = "CHUNKED"
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        event_payload = create_chunk_event(
            event_type=EVENT_DOCUMENT_CHUNKED,
            tenant_id=tenant_id,
            document_id=document_id,
            document_version_id=version_id,
            data={
                "chunk_count": len(chunk_entities),
                "strategy_used": strategy_code,
                "total_tokens": sum(c.token_count for c in chunk_entities),
                "total_characters": sum(c.character_count for c in chunk_entities),
                "processing_duration_ms": duration_ms,
            },
        )
        event_log = DocumentEventLog(
            document_id=document_id,
            event_type=EVENT_DOCUMENT_CHUNKED,
            payload=event_payload.model_dump(),
        )
        session.add(event_log)
        await session.flush()

        return chunk_entities, duration_ms

    async def get_chunks_by_document(
        self,
        tenant_id: str,
        document_id: uuid.UUID,
        session: AsyncSession,
        version_id: uuid.UUID | None = None,
        strategy_used: str | None = None,
        page: int = 1,
        size: int = 50,
    ) -> ChunkListResponse:
        """Retrieve paginated chunk listings with sequence order and relationships."""
        repo = DocumentChunkRepository(session)
        skip = (max(1, page) - 1) * size

        if version_id:
            chunks = await repo.get_chunks_by_version(tenant_id, version_id, skip, size, strategy_used)
            total = await repo.count_chunks_by_version(tenant_id, version_id, strategy_used)
            target_ver_id = version_id
        else:
            chunks = await repo.get_chunks_by_document(tenant_id, document_id, skip, size, strategy_used)
            total = await repo.count_chunks_by_document(tenant_id, document_id, strategy_used)
            target_ver_id = chunks[0].document_version_id if chunks else uuid.UUID("00000000-0000-0000-0000-000000000000")

        items = [ChunkResponse.model_validate(c) for c in chunks]
        return ChunkListResponse(
            items=items,
            total=total,
            page=page,
            size=size,
            document_id=document_id,
            document_version_id=target_ver_id,
            strategy_used=strategy_used,
        )

    async def get_chunk_by_id(self, tenant_id: str, chunk_id: uuid.UUID, session: AsyncSession) -> ChunkDetailResponse:
        """Fetch deep detail view of a single chunk including section path and relationship links."""
        repo = DocumentChunkRepository(session)
        chunk = await repo.get_by_id_and_tenant(chunk_id, tenant_id)
        if not chunk:
            raise ChunkNotFoundException(message=f"Chunk {chunk_id} not found in tenant namespace.")

        return ChunkDetailResponse.model_validate(chunk)

    async def delete_chunks_by_document(
        self,
        tenant_id: str,
        document_id: uuid.UUID,
        session: AsyncSession,
        version_id: uuid.UUID | None = None,
    ) -> int:
        """Purge chunks for a document namespace."""
        repo = DocumentChunkRepository(session)
        if version_id:
            return await repo.delete_chunks_by_version(tenant_id, version_id)
        return await repo.delete_chunks_by_document(tenant_id, document_id)

    def list_strategies(self) -> list[StrategyInfoDTO]:
        """Return available splitting strategies with parameters and MIME compatibility."""
        return self.factory.list_strategies()

    async def get_metrics(
        self,
        tenant_id: str,
        session: AsyncSession,
        document_id: uuid.UUID | None = None,
    ) -> ChunkMetricsDTO:
        """Return summary chunk KPIs across tenant or specific document."""
        repo = DocumentChunkRepository(session)
        return await repo.get_chunk_metrics(tenant_id=tenant_id, document_id=document_id)
