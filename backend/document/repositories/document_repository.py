"""Document and DocumentVersion persistence repository (`DocumentRepository`).

Isolates all SQLAlchemy ORM operations for the Document domain aggregate root (`ADR-005`).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.document.models.document import Document, DocumentVersion
from backend.models.entities.folder import Folder
from backend.document.models.status import DocumentStatus
from sqlalchemy import or_, update
import datetime


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
        stmt = select(Document).outerjoin(Folder, Document.folder_id == Folder.id).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
            Document.is_deleted.is_(False),
            or_(Document.folder_id.is_(None), Folder.is_deleted.is_(False)),
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_with_versions(
        self, document_id: uuid.UUID, tenant_id: str, session: AsyncSession
    ) -> Document | None:
        """Fetch a Document with all its related version records eager-loaded."""
        stmt = (
            select(Document)
            .outerjoin(Folder, Document.folder_id == Folder.id)
            .options(
                selectinload(Document.versions).selectinload(
                    DocumentVersion.storage_object
                )
            )
            .where(
                Document.id == document_id,
                Document.tenant_id == tenant_id,
                Document.is_deleted.is_(False),
                or_(Document.folder_id.is_(None), Folder.is_deleted.is_(False)),
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
        base_query = select(Document).outerjoin(Folder, Document.folder_id == Folder.id).where(
            Document.tenant_id == tenant_id,
            Document.is_deleted.is_(False),
            or_(Document.folder_id.is_(None), Folder.is_deleted.is_(False)),
        )
        if status:
            base_query = base_query.where(Document.status == status)
        else:
            base_query = base_query.where(Document.status != DocumentStatus.ARCHIVED.value)

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
        stmt = select(Document).outerjoin(Folder, Document.folder_id == Folder.id).where(
            Document.id == document_id, 
            Document.is_deleted.is_(False),
            or_(Document.folder_id.is_(None), Folder.is_deleted.is_(False)),
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

    async def archive_document(
        self, document_id: uuid.UUID, tenant_id: str, user_id: uuid.UUID | None, session: AsyncSession
    ) -> Document | None:
        """Archive a document."""
        doc = await self.get_by_id(document_id, tenant_id, session)
        if not doc:
            return None
        doc.status = DocumentStatus.ARCHIVED.value
        doc.archived_at = datetime.datetime.now(datetime.timezone.utc)
        doc.archived_by_user_id = user_id
        await session.flush()
        await session.refresh(doc)
        return doc

    async def restore_document(
        self, document_id: uuid.UUID, tenant_id: str, session: AsyncSession
    ) -> Document | None:
        """Restore an archived document."""
        stmt = select(Document).outerjoin(Folder, Document.folder_id == Folder.id).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
            Document.is_deleted.is_(False),
            Document.status == DocumentStatus.ARCHIVED.value,
        )
        result = await session.execute(stmt)
        doc = result.scalar_one_or_none()
        if not doc:
            return None
        doc.status = DocumentStatus.PROCESSED.value
        doc.archived_at = None
        doc.archived_by_user_id = None
        await session.flush()
        await session.refresh(doc)
        return doc

    async def get_versions_by_document_id(
        self, document_id: uuid.UUID, session: AsyncSession
    ) -> list[DocumentVersion]:
        """Fetch all DocumentVersions for a specific document."""
        stmt = (
            select(DocumentVersion)
            .options(selectinload(DocumentVersion.storage_object))
            .where(
                DocumentVersion.document_id == document_id,
                DocumentVersion.is_deleted.is_(False)
            )
            .order_by(DocumentVersion.version_number.desc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def set_active_version(
        self, document_id: uuid.UUID, version_id: uuid.UUID, session: AsyncSession
    ) -> None:
        """Set a single version as active and all others as inactive for a document."""
        # Deactivate all
        stmt_deactivate = update(DocumentVersion).where(
            DocumentVersion.document_id == document_id
        ).values(is_active_vector=False)
        await session.execute(stmt_deactivate)
        
        # Activate the specified one
        stmt_activate = update(DocumentVersion).where(
            DocumentVersion.id == version_id
        ).values(is_active_vector=True)
        await session.execute(stmt_activate)
        await session.flush()
    async def get_by_id_for_update(
        self, document_id: uuid.UUID, tenant_id: str, session: AsyncSession
    ) -> Document | None:
        """Fetch a Document by ID with a row-level lock (FOR UPDATE)."""
        stmt = select(Document).outerjoin(Folder, Document.folder_id == Folder.id).where(
            Document.id == document_id,
            Document.tenant_id == tenant_id,
            Document.is_deleted.is_(False),
            or_(Document.folder_id.is_(None), Folder.is_deleted.is_(False)),
        ).with_for_update()
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_metadata(
        self, document_id: uuid.UUID, tenant_id: str, metadata: dict, session: AsyncSession
    ) -> Document | None:
        """Replace the user_metadata dictionary entirely."""
        doc = await self.get_by_id_for_update(document_id, tenant_id, session)
        if not doc:
            return None
        doc.user_metadata = metadata
        await session.flush()
        await session.refresh(doc)
        return doc

    async def patch_metadata(
        self, document_id: uuid.UUID, tenant_id: str, patch_data: dict, session: AsyncSession
    ) -> Document | None:
        """Merge/patch new keys into user_metadata."""
        doc = await self.get_by_id_for_update(document_id, tenant_id, session)
        if not doc:
            return None
        current_metadata = dict(doc.user_metadata)
        current_metadata.update(patch_data)
        doc.user_metadata = current_metadata
        await session.flush()
        await session.refresh(doc)
        return doc

    async def remove_metadata_key(
        self, document_id: uuid.UUID, tenant_id: str, key: str, session: AsyncSession
    ) -> Document | None:
        """Remove a specific key from user_metadata."""
        doc = await self.get_by_id_for_update(document_id, tenant_id, session)
        if not doc:
            return None
        current_metadata = dict(doc.user_metadata)
        if key in current_metadata:
            del current_metadata[key]
        doc.user_metadata = current_metadata
        await session.flush()
        await session.refresh(doc)
        return doc

