"""Unit tests for Vector Storage Database Layer (`ADR-M3-001`).

Verifies `VectorIndexMetadata` ORM model properties/constraints and `VectorMetadataRepository`
CRUD/status transition methods (`get_or_create_metadata`, `update_sync_status`, `get_tenant_collection_summary`).
"""

from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.vector.models import VectorIndexMetadata
from backend.modules.vector.repositories import VectorMetadataRepository


@pytest.mark.unit
class TestVectorIndexMetadataModel:
    """Test `VectorIndexMetadata` ORM model attributes and string representation."""

    def test_model_defaults_and_repr(self) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        meta = VectorIndexMetadata(
            tenant_id="tenant-alpha",
            document_id=doc_id,
            document_version_id=ver_id,
            collection_name="raguard_knowledge_1536",
        )

        assert meta.tenant_id == "tenant-alpha"
        assert meta.document_id == doc_id
        assert meta.document_version_id == ver_id
        assert meta.collection_name == "raguard_knowledge_1536"
        assert meta.status == "PENDING"
        assert meta.points_count == 0
        assert meta.error_message is None

        repr_str = repr(meta)
        assert "raguard_knowledge_1536" in repr_str
        assert "PENDING" in repr_str


@pytest.mark.unit
@pytest.mark.asyncio
class TestVectorMetadataRepository:
    """Test `VectorMetadataRepository` database operations with mocked AsyncSession."""

    async def test_get_by_version_and_collection_found(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        ver_id = uuid.uuid4()
        mock_meta = VectorIndexMetadata(
            tenant_id="t-1",
            document_version_id=ver_id,
            collection_name="col-A",
            status="COMPLETED",
        )
        mock_result.scalar_one_or_none.return_value = mock_meta
        mock_session.execute.return_value = mock_result

        repo = VectorMetadataRepository(mock_session)
        found = await repo.get_by_version_and_collection("t-1", ver_id, "col-A")

        assert found is mock_meta
        mock_session.execute.assert_awaited_once()

    async def test_get_or_create_metadata_returns_existing(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        ver_id = uuid.uuid4()
        existing_meta = VectorIndexMetadata(
            tenant_id="t-1",
            document_version_id=ver_id,
            collection_name="col-A",
            status="PROCESSING",
        )
        mock_result.scalar_one_or_none.return_value = existing_meta
        mock_session.execute.return_value = mock_result

        repo = VectorMetadataRepository(mock_session)
        meta = await repo.get_or_create_metadata("t-1", uuid.uuid4(), ver_id, "col-A")

        assert meta is existing_meta
        mock_session.add.assert_not_called()

    async def test_get_or_create_metadata_creates_new(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        repo = VectorMetadataRepository(mock_session)
        meta = await repo.get_or_create_metadata("t-1", doc_id, ver_id, "col-A")

        assert meta.tenant_id == "t-1"
        assert meta.document_id == doc_id
        assert meta.document_version_id == ver_id
        assert meta.collection_name == "col-A"
        assert meta.status == "PENDING"
        assert meta.points_count == 0
        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited()

    async def test_update_sync_status_success(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        meta_id = uuid.uuid4()
        instance = VectorIndexMetadata(
            tenant_id="t-1",
            collection_name="col-A",
            status="PROCESSING",
            points_count=0,
            error_message="some old error",
        )
        mock_result.scalar_one_or_none.return_value = instance
        mock_session.execute.return_value = mock_result

        repo = VectorMetadataRepository(mock_session)
        updated = await repo.update_sync_status(
            metadata_id=meta_id,
            status="COMPLETED",
            points_count=45,
        )

        assert updated is not None
        assert updated.status == "COMPLETED"
        assert updated.points_count == 45
        assert updated.error_message is None
        mock_session.flush.assert_awaited()

    async def test_update_sync_status_not_found(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = VectorMetadataRepository(mock_session)
        updated = await repo.update_sync_status(uuid.uuid4(), "COMPLETED")
        assert updated is None

    async def test_list_by_tenant(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 2

        mock_items_result = MagicMock()
        items_list = [
            VectorIndexMetadata(tenant_id="t-1", status="COMPLETED"),
            VectorIndexMetadata(tenant_id="t-1", status="FAILED"),
        ]
        mock_items_result.scalars.return_value.all.return_value = items_list

        mock_session.execute.side_effect = [mock_count_result, mock_items_result]

        repo = VectorMetadataRepository(mock_session)
        items, total = await repo.list_by_tenant("t-1", status="ALL", limit=10, offset=0)

        assert total == 2
        assert len(items) == 2
        assert mock_session.execute.call_count == 2

    async def test_get_tenant_collection_summary(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()

        row1 = MagicMock()
        row1.collection_name = "raguard_knowledge_1536"
        row1.total_points = 500
        row1.total_versions = 5

        row2 = MagicMock()
        row2.collection_name = "raguard_knowledge_1024"
        row2.total_points = 200
        row2.total_versions = 2

        mock_result.all.return_value = [row1, row2]
        mock_session.execute.return_value = mock_result

        repo = VectorMetadataRepository(mock_session)
        summary = await repo.get_tenant_collection_summary("t-1")

        assert summary["tenant_id"] == "t-1"
        assert summary["total_points_stored"] == 700
        assert len(summary["collections"]) == 2
        assert summary["collections"][0]["collection_name"] == "raguard_knowledge_1536"
        assert summary["collections"][0]["total_points"] == 500
        assert summary["collections"][0]["indexed_versions_count"] == 5
