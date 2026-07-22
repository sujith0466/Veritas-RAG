"""Document and DocumentVersion persistence repository (`DocumentRepository`).

Isolates all SQLAlchemy ORM operations for the Document domain aggregate root (`ADR-005`).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.document.models.document import Document, DocumentVersion


class DocumentRepository:
    """Repository for CRUD operations on Document and DocumentVersion entities."""

    async def create(self, document: Document, session: AsyncSession) -> Document:
        """Persist a new Document aggregate to the database."""
        session.add(document)
        await session.flush()
        await session.refresh(document)
        return document

    async def get_by_id(
        self, document_id: uuid.UUID, tenant_id: str, session: AsyncSession
    ) -> Document | None:
        """Fetch a Document by ID and tenant ID namespace."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
            Document.is_deleted.is_(False),
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_with_versions(
        self, document_id: uuid.UUID, tenant_id: str, session: AsyncSession
    ) -> Document | None:
        """Fetch a Document with all its related version records eager-loaded."""
        stmt = (
            select(Document)
            .options(
                selectinload(Document.versions).selectinload(
                    DocumentVersion.storage_object
                )
            )
            .where(
                Document.id == document_id,
                Document.tenant_id == tenant_id,
                Document.is_deleted.is_(False),
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        tenant_id: str,
        session: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[Document], int]:
        """List documents within a tenant namespace with pagination and optional status filter."""
        base_query = select(Document).where(
            Document.tenant_id == tenant_id,
            Document.is_deleted.is_(False),
        )
        if status:
            base_query = base_query.where(Document.status == status)

        # Count total
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total_result = await session.execute(count_stmt)
        total = total_result.scalar_one() or 0

        # Paginate
        items_stmt = (
            base_query.order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items_result = await session.execute(items_stmt)
        items = list(items_result.scalars().all())

        return items, total

    async def update_status(
        self, document_id: uuid.UUID, status: str, session: AsyncSession
    ) -> Document | None:
        """Update the processing status of a document."""
        stmt = select(Document).where(
            Document.id == document_id, Document.is_deleted.is_(False)
        )
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if doc:
            doc.status = status
            await session.flush()
            await session.refresh(doc)
        return doc

    async def add_version(
        self, version: DocumentVersion, session: AsyncSession
    ) -> DocumentVersion:
        """Add and persist a new DocumentVersion record."""
        session.add(version)
        await session.flush()
        await session.refresh(version)
        return version

    async def get_version_by_id(
        self, version_id: uuid.UUID, session: AsyncSession
    ) -> DocumentVersion | None:
        """Fetch a specific DocumentVersion by its ID."""
        stmt = (
            select(DocumentVersion)
            .options(selectinload(DocumentVersion.storage_object))
            .where(
                DocumentVersion.id == version_id, DocumentVersion.is_deleted.is_(False)
            )
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(
        self, document_id: uuid.UUID, tenant_id: str, session: AsyncSession
    ) -> bool:
        """Soft-delete a document by setting `is_deleted = True`."""
        doc = await self.get_by_id(document_id, tenant_id, session)
        if not doc:
            return False
        doc.is_deleted = True
        await session.flush()
        return True
