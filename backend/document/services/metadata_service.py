"""Metadata Service.

Handles document metadata updates, validation, Redis locking, and Qdrant synchronization triggers.
"""

from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.redis_client import acquire_lock
from backend.document.repositories.document_repository import DocumentRepository
from backend.document.services.exceptions import DocumentDomainException


class MetadataService:
    """Service for managing document metadata."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the service."""
        self.session = session
        self.repository = DocumentRepository()

    def _validate_metadata(self, metadata: dict[str, Any]) -> None:
        """Validate metadata payload against system rules."""
        if len(metadata) > 100:
            raise DocumentDomainException("VAL_001", "Maximum of 100 metadata keys allowed.")
        for key, value in metadata.items():
            if key.startswith("__"):
                raise DocumentDomainException("VAL_001", f"Key '{key}' is reserved for system use.")
            if len(key) > 64:
                raise DocumentDomainException("VAL_001", f"Key '{key}' exceeds maximum length of 64 characters.")
            if isinstance(value, str) and len(value) > 512:
                raise DocumentDomainException("VAL_001", f"Value for key '{key}' exceeds maximum length of 512 characters.")
            if not isinstance(value, (str, int, float, bool)) and value is not None:
                raise DocumentDomainException("VAL_001", f"Unsupported value type for key '{key}'.")

    async def update_metadata(
        self, document_id: uuid.UUID, tenant_id: str, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Overwrite the document's metadata entirely."""
        self._validate_metadata(metadata)

        async with acquire_lock(f"ws:{tenant_id}:doc:{document_id}"):
            doc = await self.repository.update_metadata(document_id, tenant_id, metadata, self.session)
            if not doc:
                raise DocumentDomainException("STORE_002", "Document not found.")
            # Event publishing and Celery task will be called at the router level or here
            return doc.user_metadata

    async def patch_metadata(
        self, document_id: uuid.UUID, tenant_id: str, patch_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge new keys into the document's metadata."""
        self._validate_metadata(patch_data)

        async with acquire_lock(f"ws:{tenant_id}:doc:{document_id}"):
            # Need to get the document first to check the combined size limit, but we can rely on repository patch
            doc = await self.repository.patch_metadata(document_id, tenant_id, patch_data, self.session)
            if not doc:
                raise DocumentDomainException("STORE_002", "Document not found.")
            if len(doc.user_metadata) > 100:
                raise DocumentDomainException("VAL_001", "Maximum of 100 metadata keys allowed after patch.")
            return doc.user_metadata

    async def remove_metadata_key(
        self, document_id: uuid.UUID, tenant_id: str, key: str
    ) -> dict[str, Any]:
        """Remove a specific metadata key."""
        async with acquire_lock(f"ws:{tenant_id}:doc:{document_id}"):
            doc = await self.repository.remove_metadata_key(document_id, tenant_id, key, self.session)
            if not doc:
                raise DocumentDomainException("STORE_002", "Document not found.")
            return doc.user_metadata
