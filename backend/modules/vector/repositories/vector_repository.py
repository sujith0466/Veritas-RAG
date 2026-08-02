"""Vector metadata repository implementation (`VectorMetadataRepository`).

Provides asynchronous CRUD access, status transitions, and tenant point summaries
for `VectorIndexMetadata` entities inside PostgreSQL (`ADR-M3-001`).
"""

from collections.abc import Sequence
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.modules.vector.models.vector_metadata import VectorIndexMetadata
from backend.repositories.base import BaseRepository

logger = structlog.get_logger(__name__)


class VectorMetadataRepository(BaseRepository[VectorIndexMetadata]):
    """Repository for managing `VectorIndexMetadata` entities (`ADR-M3-001`)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session=session, model_class=VectorIndexMetadata)

    async def get_by_version_and_collection(
        self,
        tenant_id: str,
        document_version_id: uuid.UUID | str,
        collection_name: str,
    ) -> VectorIndexMetadata | None:
        """Retrieve index metadata by tenant, document version, and Qdrant collection name."""
        ver_uuid = (
            document_version_id
            if isinstance(document_version_id, uuid.UUID)
            else uuid.UUID(str(document_version_id))
        )
        stmt = select(VectorIndexMetadata).where(
            VectorIndexMetadata.tenant_id == tenant_id,
            VectorIndexMetadata.document_version_id == ver_uuid,
            VectorIndexMetadata.collection_name == collection_name,
            VectorIndexMetadata.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_metadata(
        self,
        tenant_id: str,
        document_id: uuid.UUID | str,
        document_version_id: uuid.UUID | str,
        collection_name: str,
    ) -> VectorIndexMetadata:
        """Fetch existing index metadata or create a new entry in PENDING status."""
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

        existing = await self.get_by_version_and_collection(
            tenant_id=tenant_id,
            document_version_id=ver_uuid,
            collection_name=collection_name,
        )
        if existing is not None:
            return existing

        logger.debug(
            "Creating new VectorIndexMetadata record",
            tenant_id=tenant_id,
            version_id=str(ver_uuid),
            collection=collection_name,
        )
        return await self.create(
            tenant_id=tenant_id,
            document_id=doc_uuid,
            document_version_id=ver_uuid,
            collection_name=collection_name,
            status="PENDING",
            points_count=0,
        )

    async def update_sync_status(
        self,
        metadata_id: uuid.UUID | str | None,
        status: str,
        points_count: int | None = None,
        error_message: str | None = None,
    ) -> VectorIndexMetadata | None:
        """Update synchronization status, points count, and error details."""
        if metadata_id is None:
            return None
        meta_uuid = (
            metadata_id
            if isinstance(metadata_id, uuid.UUID)
            else uuid.UUID(str(metadata_id))
        )
        instance = await self.get_by_id(meta_uuid)
        if instance is None:
            return None

        update_kwargs: dict[str, Any] = {"status": status.upper()}
        if points_count is not None:
            update_kwargs["points_count"] = points_count
        if error_message is not None:
            update_kwargs["error_message"] = error_message
        elif status.upper() == "COMPLETED":
            update_kwargs["error_message"] = None

        return await self.update(instance, **update_kwargs)

    async def list_by_tenant(
        self,
        tenant_id: str,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[Sequence[VectorIndexMetadata], int]:
        """Paginated listing of vector index metadata records for a tenant."""
        query = select(VectorIndexMetadata).where(
            VectorIndexMetadata.tenant_id == tenant_id,
            VectorIndexMetadata.is_deleted.is_(False),
        )
        if status and status.upper() != "ALL":
            query = query.where(VectorIndexMetadata.status == status.upper())

        count_stmt = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        paginated_stmt = (
            query.order_by(VectorIndexMetadata.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = (await self.session.execute(paginated_stmt)).scalars().all()
        return items, total

    async def get_tenant_collection_summary(self, tenant_id: str) -> dict[str, Any]:
        """Compute aggregate vector point metrics across collections for a tenant namespace."""
        stmt = (
            select(
                VectorIndexMetadata.collection_name,
                func.sum(VectorIndexMetadata.points_count).label("total_points"),
                func.count(VectorIndexMetadata.id).label("total_versions"),
            )
            .where(
                VectorIndexMetadata.tenant_id == tenant_id,
                VectorIndexMetadata.status == "COMPLETED",
                VectorIndexMetadata.is_deleted.is_(False),
            )
            .group_by(VectorIndexMetadata.collection_name)
        )
        results = (await self.session.execute(stmt)).all()

        collections = []
        total_points_all = 0
        for row in results:
            points = int(row.total_points or 0)
            total_points_all += points
            collections.append(
                {
                    "collection_name": row.collection_name,
                    "total_points": points,
                    "indexed_versions_count": int(row.total_versions or 0),
                }
            )

        return {
            "tenant_id": tenant_id,
            "total_points_stored": total_points_all,
            "collections": collections,
        }
