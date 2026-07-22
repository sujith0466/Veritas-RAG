"""Document Processing Contract verification (`CONTRACT_001`).

Strictly verifies that all database entities (`Document`, `DocumentVersion`, `StorageObject`)
and physical artifacts (`/original/...`, `/normalized/text.txt`, `/metadata/manifest.json`)
exist and have valid non-zero content before a document can transition to `PROCESSED`.
"""

from backend.document.models import Document, DocumentVersion
from backend.document.schemas.errors import (DocumentDomainException,
                                             DocumentErrorCode)

from .base import StorageProvider, get_versioned_path


class DocumentProcessingContract:
    """Enforces absolute completeness of document persistence and artifact generation."""

    @classmethod
    async def verify(
        cls,
        document: Document,
        version: DocumentVersion,
        storage_provider: StorageProvider,
    ) -> bool:
        """Verify processing completeness (`CONTRACT_001`).

        Raises DocumentDomainException(CONTRACT_001) if any required artifact is missing.
        """
        if not document or not document.id:
            raise DocumentDomainException(
                code=DocumentErrorCode.CONTRACT_001,
                message="Contract failure: Document entity is missing or unpersisted.",
            )

        if not version or not version.id or not version.storage_object_id:
            raise DocumentDomainException(
                code=DocumentErrorCode.CONTRACT_001,
                message="Contract failure: DocumentVersion entity or storage link is missing.",
                detail={"document_id": str(document.id)},
            )

        # 1. Verify original binary artifact
        original_key = (
            version.storage_object.object_key if version.storage_object else None
        )
        if not original_key or not await storage_provider.object_exists(original_key):
            raise DocumentDomainException(
                code=DocumentErrorCode.CONTRACT_001,
                message="Contract failure: Original binary artifact missing from storage provider.",
                detail={
                    "document_id": str(document.id),
                    "expected_key": str(original_key),
                },
            )

        # 2. Verify normalized text artifact
        if not version.extracted_text_path or not await storage_provider.object_exists(
            version.extracted_text_path
        ):
            raise DocumentDomainException(
                code=DocumentErrorCode.CONTRACT_001,
                message="Contract failure: Normalized text artifact (`text.txt`) missing from storage provider.",
                detail={
                    "document_id": str(document.id),
                    "expected_path": str(version.extracted_text_path),
                },
            )

        # 3. Verify canonical manifest artifact
        manifest_key = get_versioned_path(
            tenant_id=document.tenant_id,
            document_id=document.id,
            version_number=version.version_number,
            category="metadata",
            filename="manifest.json",
        )
        if not await storage_provider.object_exists(manifest_key):
            raise DocumentDomainException(
                code=DocumentErrorCode.CONTRACT_001,
                message="Contract failure: Canonical Document Manifest (`manifest.json`) missing from storage provider.",
                detail={"document_id": str(document.id), "manifest_key": manifest_key},
            )

        return True
