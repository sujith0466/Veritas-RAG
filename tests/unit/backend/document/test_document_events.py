"""Unit tests for Document Domain Event Payloads and Versioning (`Refinement 4`)."""

import uuid

from backend.document.events.domain_events import (
    EVENT_DOCUMENT_FAILED,
    EVENT_DOCUMENT_PROCESSED,
    EVENT_DOCUMENT_UPLOADED,
    create_domain_event,
)


class TestDocumentEvents:
    """Test suite verifying versioned domain event payloads."""

    def test_create_domain_event_schema_version(self):
        """Verify DomainEventPayload enforces schema_version 1.0.0 (`Refinement 4`)."""
        doc_id = uuid.uuid4()
        job_id = uuid.uuid4()
        event = create_domain_event(
            event_type=EVENT_DOCUMENT_UPLOADED,
            tenant_id="tenant-a",
            document_id=doc_id,
            job_id=job_id,
            data={"filename": "report.pdf", "size": 50000},
        )
        assert event.schema_version == "1.0.0"
        assert event.event_type == EVENT_DOCUMENT_UPLOADED
        assert event.tenant_id == "tenant-a"
        assert event.document_id == doc_id
        assert event.job_id == job_id
        assert event.data["filename"] == "report.pdf"

    def test_processed_event_payload(self):
        """Verify processed event captures required attributes."""
        doc_id = uuid.uuid4()
        event = create_domain_event(
            event_type=EVENT_DOCUMENT_PROCESSED,
            tenant_id="tenant-b",
            document_id=doc_id,
            data={"word_count": 420, "page_count": 2},
        )
        assert event.schema_version == "1.0.0"
        assert event.event_type == "DocumentProcessed"
        assert event.data["word_count"] == 420

    def test_failed_event_payload(self):
        """Verify failed event classification."""
        doc_id = uuid.uuid4()
        event = create_domain_event(
            event_type=EVENT_DOCUMENT_FAILED,
            tenant_id="tenant-c",
            document_id=doc_id,
            data={"error_code": "VAL_002", "failed_stage": "validation"},
        )
        assert event.schema_version == "1.0.0"
        assert event.event_type == "DocumentFailed"
        assert event.data["error_code"] == "VAL_002"
