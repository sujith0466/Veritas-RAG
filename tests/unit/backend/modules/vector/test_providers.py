"""Unit tests for Vector Storage Provider Layer (`ADR-004`).

Tests `BaseVectorDBProvider` contract, `QdrantVectorDBProvider` HNSW/INT8 setup,
payload index creation, error taxonomy mapping (`VEC_001` to `VEC_005`), and `VectorProviderFactory`.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models

from backend.modules.vector.providers import (
    QdrantVectorDBProvider,
    VectorProviderFactory,
)
from backend.modules.vector.schemas import (
    CollectionConfigDTO,
    CollectionNotFoundError,
    DimensionMismatchError,
    InvalidPayloadSchemaError,
    QdrantConnectionError,
    VectorPointDTO,
)


@pytest.fixture
def mock_qdrant_client() -> AsyncMock:
    """Fixture providing a mock AsyncQdrantClient."""
    mock = AsyncMock(spec=AsyncQdrantClient)
    return mock


@pytest.fixture
def provider(mock_qdrant_client: AsyncMock) -> QdrantVectorDBProvider:
    """Fixture providing a QdrantVectorDBProvider with mock client."""
    return QdrantVectorDBProvider(client=mock_qdrant_client)


class TestVectorProviderFactory:
    """Test `VectorProviderFactory` resolution and caching."""

    def test_get_provider_default_qdrant(self, mock_qdrant_client: AsyncMock) -> None:
        VectorProviderFactory.clear_cache()
        prov = VectorProviderFactory.get_provider("qdrant", client=mock_qdrant_client)
        assert isinstance(prov, QdrantVectorDBProvider)
        assert prov.provider_name == "qdrant"

    def test_get_provider_unsupported_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported vector database provider engine"):
            VectorProviderFactory.get_provider("pinecone")


@pytest.mark.asyncio
class TestQdrantVectorDBProvider:
    """Test `QdrantVectorDBProvider` HNSW setup, INT8 quantization, and operations."""

    async def test_ensure_collection_already_exists(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        mock_qdrant_client.collection_exists.return_value = True
        config = CollectionConfigDTO(collection_name="test_col", dimension=1536)

        result = await provider.ensure_collection(config)
        assert result is True
        mock_qdrant_client.collection_exists.assert_called_once_with(collection_name="test_col")
        mock_qdrant_client.create_collection.assert_not_called()

    async def test_ensure_collection_creates_with_int8_quantization(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        mock_qdrant_client.collection_exists.return_value = False
        config = CollectionConfigDTO(
            collection_name="test_col",
            dimension=1024,
            distance_metric="Cosine",
            scalar_quantization=True,
        )

        result = await provider.ensure_collection(config)
        assert result is True
        mock_qdrant_client.create_collection.assert_called_once()
        _, kwargs = mock_qdrant_client.create_collection.call_args
        assert kwargs["collection_name"] == "test_col"
        assert kwargs["vectors_config"].size == 1024
        assert kwargs["vectors_config"].distance == qdrant_models.Distance.COSINE
        assert kwargs["quantization_config"].scalar.type == qdrant_models.ScalarType.INT8
        assert kwargs["quantization_config"].scalar.always_ram is True

    async def test_ensure_collection_raises_connection_error(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        mock_qdrant_client.collection_exists.side_effect = RuntimeError("gRPC transport error")
        config = CollectionConfigDTO(collection_name="test_col", dimension=1536)

        with pytest.raises(QdrantConnectionError) as exc_info:
            await provider.ensure_collection(config)
        assert exc_info.value.code == "VEC_003"
        assert exc_info.value.http_status == 503

    async def test_create_payload_indexes(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        mock_qdrant_client.create_payload_index.return_value = MagicMock()

        result = await provider.create_payload_indexes(
            collection_name="test_col",
            indexed_fields=["tenant_id", "document_id"],
        )
        assert result is True
        assert mock_qdrant_client.create_payload_index.call_count == 2

    async def test_create_payload_indexes_safe_on_already_exists(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        mock_qdrant_client.create_payload_index.side_effect = RuntimeError("Index already exists")

        result = await provider.create_payload_indexes(
            collection_name="test_col",
            indexed_fields=["tenant_id"],
        )
        assert result is True

    async def test_upsert_points_success(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        mock_qdrant_client.upsert.return_value = MagicMock(status=qdrant_models.UpdateStatus.COMPLETED)
        points = [
            VectorPointDTO(
                point_id="123e4567-e89b-12d3-a456-426614174000",
                vector=[0.1, 0.2, -0.5],
                payload={
                    "tenant_id": "tenant-1",
                    "document_id": "doc-1",
                    "document_version_id": "ver-1",
                    "content_hash": "sha-123",
                },
            )
        ]

        count = await provider.upsert_points("test_col", points)
        assert count == 1
        mock_qdrant_client.upsert.assert_called_once()
        _, kwargs = mock_qdrant_client.upsert.call_args
        assert kwargs["collection_name"] == "test_col"
        assert len(kwargs["points"]) == 1
        assert kwargs["points"][0].id == "123e4567-e89b-12d3-a456-426614174000"
        assert kwargs["points"][0].vector == [0.1, 0.2, -0.5]

    async def test_upsert_points_empty_list_returns_zero(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        assert await provider.upsert_points("test_col", []) == 0
        mock_qdrant_client.upsert.assert_not_called()

    async def test_upsert_points_error_mapping(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        point = VectorPointDTO(
            point_id="123e4567-e89b-12d3-a456-426614174000",
            vector=[0.1],
            payload={"tenant_id": "t", "document_id": "d", "document_version_id": "v", "content_hash": "h"},
        )

        # 1. Collection not found
        mock_qdrant_client.upsert.side_effect = Exception("Collection test_col not found")
        with pytest.raises(CollectionNotFoundError) as exc_info:
            await provider.upsert_points("test_col", [point])
        assert exc_info.value.code == "VEC_002"

        # 2. Dimension mismatch
        mock_qdrant_client.upsert.side_effect = Exception("wrong vector size mismatch")
        with pytest.raises(DimensionMismatchError) as exc_info:
            await provider.upsert_points("test_col", [point])
        assert exc_info.value.code == "VEC_004"

        # 3. Payload schema error
        mock_qdrant_client.upsert.side_effect = Exception("payload schema invalid")
        with pytest.raises(InvalidPayloadSchemaError) as exc_info:
            await provider.upsert_points("test_col", [point])
        assert exc_info.value.code == "VEC_001"

    async def test_delete_points_by_filter(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        mock_qdrant_client.delete.return_value = MagicMock(operation_id=42)

        op_id = await provider.delete_points_by_filter(
            collection_name="test_col",
            filter_conditions={"tenant_id": "tenant-1", "document_id": "doc-1"},
        )
        assert op_id == 42
        mock_qdrant_client.delete.assert_called_once()
        _, kwargs = mock_qdrant_client.delete.call_args
        selector = kwargs["points_selector"]
        assert len(selector.filter.must) == 2

    async def test_get_collection_info(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        mock_info = MagicMock()
        mock_info.points_count = 1500
        mock_info.indexed_vectors_count = 1490
        mock_info.status.name = "GREEN"
        mock_info.config.params.vectors = qdrant_models.VectorParams(
            size=1536, distance=qdrant_models.Distance.COSINE
        )
        mock_qdrant_client.get_collection.return_value = mock_info

        summary = await provider.get_collection_info("test_col")
        assert summary.collection_name == "test_col"
        assert summary.points_count == 1500
        assert summary.indexed_vectors_count == 1490
        assert summary.status == "GREEN"
        assert summary.vector_dimension == 1536

    async def test_get_collection_info_not_found(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        mock_qdrant_client.get_collection.side_effect = Exception("Collection doesn't exist")

        with pytest.raises(CollectionNotFoundError) as exc_info:
            await provider.get_collection_info("test_col")
        assert exc_info.value.code == "VEC_002"
