from datetime import datetime
from uuid import UUID

from sqlalchemy import case as sa_case
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.document.models import Document, DocumentVersion, StorageObject
from backend.modules.chunking.models import DocumentChunk
from backend.modules.knowledge_base.schemas.knowledge_base_dto import (
    DocumentKnowledgeStatusDTO,
    KnowledgeBaseOverviewDTO,
    VectorParityValidationDTO,
)
from backend.vector_db.client import get_qdrant_client


class KnowledgeBaseService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.qdrant = get_qdrant_client()
        self.settings = get_settings()

    def _get_collection_name(self, workspace_id: UUID) -> str:
        return f"workspace_{workspace_id}_vectors"

    async def get_overview(self, workspace_id: UUID) -> KnowledgeBaseOverviewDTO:
        # Document counts
        doc_counts_stmt = select(
            func.count(Document.id).label("total"),
            func.sum(sa_case((not Document.is_deleted, 1), else_=0)).label("active"),
        ).where(Document.tenant_id == workspace_id)

        doc_res = await self.session.execute(doc_counts_stmt)
        total_docs, active_docs = doc_res.one_or_none() or (0, 0)
        total_docs = total_docs or 0
        active_docs = active_docs or 0

        # Chunk counts for active documents
        chunk_count_stmt = (
            select(func.count(DocumentChunk.id))
            .join(DocumentVersion, DocumentChunk.document_version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                Document.tenant_id == workspace_id,
                not Document.is_deleted,
                Document.active_version_id == DocumentVersion.id,
            )
        )
        chunk_res = await self.session.execute(chunk_count_stmt)
        total_chunks = chunk_res.scalar() or 0

        # Storage size and MIME distribution
        storage_stmt = (
            select(
                StorageObject.mime_type,
                func.count(StorageObject.id).label("count"),
                func.sum(StorageObject.size_bytes).label("total_bytes"),
            )
            .where(StorageObject.tenant_id == workspace_id)
            .group_by(StorageObject.mime_type)
        )
        storage_res = await self.session.execute(storage_stmt)

        mime_distribution = {}
        total_storage_bytes = 0
        for row in storage_res.all():
            mime_type, count, total_bytes = row
            mime_distribution[mime_type] = count
            total_storage_bytes += total_bytes or 0

        # Qdrant Vector count
        total_vectors = 0
        try:
            collection_name = self._get_collection_name(workspace_id)
            # Async qdrant client is needed. The project uses qdrant_client.AsyncQdrantClient
            q_count = await self.qdrant.count(collection_name=collection_name, exact=True)
            total_vectors = q_count.count
        except Exception:
            # Collection might not exist yet
            pass

        return KnowledgeBaseOverviewDTO(
            workspace_id=workspace_id,
            total_documents=total_docs,
            active_documents=active_docs,
            total_chunks=total_chunks,
            total_vectors_in_qdrant=total_vectors,
            total_storage_bytes=total_storage_bytes,
            mime_type_distribution=mime_distribution,
            stale_document_count=0,  # Will be populated by StalenessService
            last_indexed_at=datetime.utcnow() if total_vectors > 0 else None
        )

    async def get_documents_status(
        self, workspace_id: UUID, limit: int = 50, offset: int = 0
    ) -> tuple[list[DocumentKnowledgeStatusDTO], int]:

        base_stmt = select(Document, DocumentVersion).join(
            DocumentVersion, Document.active_version_id == DocumentVersion.id
        ).where(
            Document.tenant_id == workspace_id,
            not Document.is_deleted
        )

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        count_res = await self.session.execute(count_stmt)
        total_count = count_res.scalar() or 0

        docs_stmt = base_stmt.limit(limit).offset(offset)
        docs_res = await self.session.execute(docs_stmt)

        dtos = []
        for doc, ver in docs_res.all():
            # Get chunk count
            chunk_stmt = select(func.count(DocumentChunk.id)).where(
                DocumentChunk.document_version_id == ver.id
            )
            c_res = await self.session.execute(chunk_stmt)
            chunk_count = c_res.scalar() or 0

            # Get user metadata for staleness
            user_meta = doc.user_metadata or {}

            dtos.append(
                DocumentKnowledgeStatusDTO(
                    document_id=doc.id,
                    version_id=ver.id,
                    filename=doc.name,
                    status=doc.status,
                    chunk_count=chunk_count,
                    is_stale=user_meta.get("is_stale", False),
                    freshness_score=user_meta.get("freshness_score", 100.0),
                    last_indexed_at=ver.created_at
                )
            )
        return dtos, total_count

    async def validate_vector_parity(self, workspace_id: UUID) -> VectorParityValidationDTO:
        # Get active chunk count
        chunk_count_stmt = (
            select(func.count(DocumentChunk.id))
            .join(DocumentVersion, DocumentChunk.document_version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                Document.tenant_id == workspace_id,
                not Document.is_deleted,
                Document.active_version_id == DocumentVersion.id,
            )
        )
        chunk_res = await self.session.execute(chunk_count_stmt)
        active_chunks = chunk_res.scalar() or 0

        # Get Qdrant point count
        qdrant_points = 0
        try:
            collection_name = self._get_collection_name(workspace_id)
            q_count = await self.qdrant.count(collection_name=collection_name, exact=True)
            qdrant_points = q_count.count
        except Exception:
            pass

        discrepancy = abs(active_chunks - qdrant_points)
        is_parity = discrepancy == 0

        return VectorParityValidationDTO(
            workspace_id=workspace_id,
            postgres_active_chunk_count=active_chunks,
            qdrant_point_count=qdrant_points,
            is_in_parity=is_parity,
            discrepancy_count=discrepancy
        )
