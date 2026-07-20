"""Unit tests for Document Storage Path Generation and Layout (`Refinement 2`)."""

import uuid

from backend.document.storage.base import get_versioned_path


class TestDocumentStorageLayout:
    """Test suite verifying versioned storage segregation without cloud dependency."""

    def test_get_versioned_path_segregation(self):
        """Verify exact versioned directory segregation for original, normalized, and metadata (`Refinement 2`)."""
        doc_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
        tenant_id = "tenant-xyz"

        original_path = get_versioned_path(tenant_id, doc_id, 1, "original", "invoice_2026.pdf")
        normalized_path = get_versioned_path(tenant_id, doc_id, 1, "normalized", "text.txt")
        metadata_path = get_versioned_path(tenant_id, doc_id, 1, "metadata", "manifest.json")

        assert original_path == f"documents/tenant-xyz/{doc_id}/v1/original/invoice_2026.pdf"
        assert normalized_path == f"documents/tenant-xyz/{doc_id}/v1/normalized/text.txt"
        assert metadata_path == f"documents/tenant-xyz/{doc_id}/v1/metadata/manifest.json"
