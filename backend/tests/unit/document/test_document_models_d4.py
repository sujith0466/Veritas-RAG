from __future__ import annotations

import datetime
import importlib
import uuid

from backend.document.models.document import Document
from backend.document.models.status import DocumentStatus

migration_d4 = importlib.import_module(
    "backend.database.migrations.versions.20261002_add_document_source_type_and_url_fields"
)


class TestDocumentStatusEnum:
    """Tests for DocumentStatus enum values and lifecycle integration."""

    def test_fetching_status_value_and_type(self) -> None:
        assert DocumentStatus.FETCHING == "FETCHING"
        assert DocumentStatus.FETCHING.value == "FETCHING"
        assert isinstance(DocumentStatus.FETCHING, DocumentStatus)
        assert isinstance(DocumentStatus.FETCHING, str)

    def test_status_enum_complete_lifecycle_members(self) -> None:
        expected_members = {
            "UPLOADED",
            "FETCHING",
            "VALIDATING",
            "EXTRACTING",
            "OCR",
            "MANIFEST_GENERATING",
            "PROCESSED",
            "CHUNKING",
            "CHUNKED",
            "EMBEDDING",
            "EMBEDDED",
            "VECTOR_SYNC",
            "READY",
            "FAILED",
            "PENDING",
            "DELETED",
            "ARCHIVED",
        }
        actual_members = {s.value for s in DocumentStatus}
        assert expected_members.issubset(actual_members)


class TestDocumentModelD4Fields:
    """Tests for Document model columns, defaults, and website ingestion metadata."""

    def test_document_model_defaults_for_file_upload(self) -> None:
        source_type_col = Document.__table__.columns["source_type"]
        assert source_type_col.default.arg == "file_upload"
        assert source_type_col.server_default.arg == "file_upload"
        assert source_type_col.nullable is False

        doc = Document(
            id=uuid.uuid4(),
            tenant_id="tenant-123",
            filename="document.pdf",
            original_filename="document.pdf",
            source_type="file_upload",
            status=DocumentStatus.PENDING,
        )
        assert doc.source_type == "file_upload"
        assert doc.source_url is None
        assert doc.canonical_url is None
        assert doc.final_url is None
        assert doc.last_fetched_at is None
        assert doc.status == DocumentStatus.PENDING

    def test_document_model_explicit_website_source(self) -> None:
        now = datetime.datetime.now(datetime.UTC)
        doc = Document(
            id=uuid.uuid4(),
            tenant_id="tenant-abc",
            filename="page.html",
            original_filename="https://example.com/docs",
            status=DocumentStatus.FETCHING,
            source_type="website",
            source_url="https://example.com/docs",
            canonical_url="https://example.com/docs/canonical",
            final_url="https://example.com/docs/redirected",
            last_fetched_at=now,
        )
        assert doc.source_type == "website"
        assert doc.source_url == "https://example.com/docs"
        assert doc.canonical_url == "https://example.com/docs/canonical"
        assert doc.final_url == "https://example.com/docs/redirected"
        assert doc.last_fetched_at == now
        assert doc.status == DocumentStatus.FETCHING

    def test_document_table_column_definitions(self) -> None:
        columns = Document.__table__.columns

        assert "source_type" in columns
        assert columns["source_type"].nullable is False
        assert columns["source_type"].type.length == 50

        assert "source_url" in columns
        assert columns["source_url"].nullable is True
        assert columns["source_url"].type.length == 2048

        assert "canonical_url" in columns
        assert columns["canonical_url"].nullable is True
        assert columns["canonical_url"].type.length == 2048

        assert "final_url" in columns
        assert columns["final_url"].nullable is True
        assert columns["final_url"].type.length == 2048

        assert "last_fetched_at" in columns
        assert columns["last_fetched_at"].nullable is True
        assert columns["last_fetched_at"].type.timezone is True


class TestD4AlembicMigration:
    """Tests for D4 Alembic migration structure and dependency chain."""

    def test_migration_revision_identifiers(self) -> None:
        assert migration_d4.revision == "d4_001_source_url"
        assert migration_d4.down_revision == "d2_001_job_dispatch"
        assert callable(migration_d4.upgrade)
        assert callable(migration_d4.downgrade)
