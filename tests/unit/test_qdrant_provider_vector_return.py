"""Unit tests for Qdrant vector return suppression (REC-008).

Verifies that `QdrantVectorDBProvider.search_points` explicitly requests
`with_vectors=False` to defend against library default drift, while preserving
point IDs, scores, and payload mappings according to the provider contract.
"""

from unittest.mock import AsyncMock, MagicMock
from typing import Any

import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models

from backend.modules.vector.providers import QdrantVectorDBProvider


@pytest.fixture
def mock_qdrant_client() -> AsyncMock:
    """Fixture providing a mock AsyncQdrantClient."""
    return AsyncMock(spec=AsyncQdrantClient)


@pytest.fixture
def provider(mock_qdrant_client: AsyncMock) -> QdrantVectorDBProvider:
    """Fixture providing a QdrantVectorDBProvider with mock client."""
    return QdrantVectorDBProvider(client=mock_qdrant_client)


@pytest.mark.asyncio
class TestQdrantVectorReturnOptimization:
    """Test explicit vector-return suppression in `QdrantVectorDBProvider.search_points`."""

    async def test_search_points_explicitly_passes_with_vectors_false(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        """Verify search_points explicitly supplies with_vectors=False to client.search."""
        mock_hit = MagicMock()
        mock_hit.id = "point-uuid-1"
        mock_hit.score = 0.92
        mock_hit.payload = {
            "chunk_id": "chunk-1",
            "document_id": "doc-1",
            "tenant_id": "tenant-alpha",
            "content": "Sample verified document chunk.",
        }
        mock_hit.vector = None
        mock_qdrant_client.search.return_value = [mock_hit]

        results = await provider.search_points(
            collection_name="raguard_knowledge_tenant-alpha",
            query_vector=[0.12, -0.45, 0.88],
            filter_conditions={"tenant_id": "tenant-alpha"},
            limit=25,
            offset=5,
        )

        mock_qdrant_client.search.assert_called_once()
        _, kwargs = mock_qdrant_client.search.call_args

        # REC-008 core verification
        assert "with_vectors" in kwargs, "with_vectors parameter must be explicitly passed"
        assert kwargs["with_vectors"] is False, "with_vectors must be explicitly False"

        # Contract preservation checks
        assert kwargs["collection_name"] == "raguard_knowledge_tenant-alpha"
        assert kwargs["query_vector"] == [0.12, -0.45, 0.88]
        assert kwargs["limit"] == 25
        assert kwargs["offset"] == 5
        assert kwargs["with_payload"] is True
        assert isinstance(kwargs["query_filter"], qdrant_models.Filter)
        assert len(kwargs["query_filter"].must) == 1

        # Return mapping checks
        assert len(results) == 1
        assert results[0]["point_id"] == "point-uuid-1"
        assert results[0]["score"] == 0.92
        assert results[0]["payload"]["chunk_id"] == "chunk-1"
        assert results[0]["payload"]["content"] == "Sample verified document chunk."
        assert "vector" not in results[0], "Candidate result must not contain vector field"

    async def test_search_points_maps_results_when_vector_is_absent(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        """Verify mapping succeeds when ScoredPoint has vector=None (server-side suppressed)."""
        hit_1 = MagicMock(id="p-1", score=0.85, payload={"text": "chunk one"}, vector=None)
        hit_2 = MagicMock(id="p-2", score=0.74, payload={"text": "chunk two"}, vector=None)
        mock_qdrant_client.search.return_value = [hit_1, hit_2]

        results = await provider.search_points(
            collection_name="col_test",
            query_vector=[0.5, -0.5],
            filter_conditions={},
            limit=10,
        )

        assert len(results) == 2
        assert results[0] == {"point_id": "p-1", "score": 0.85, "payload": {"text": "chunk one"}}
        assert results[1] == {"point_id": "p-2", "score": 0.74, "payload": {"text": "chunk two"}}

    async def test_search_points_ignores_vector_field_if_populated(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        """Verify provider output contract does not expose vectors even if present on hit."""
        hit = MagicMock(id="p-vec", score=0.99, payload={"k": "v"}, vector=[0.1, 0.2, 0.3])
        mock_qdrant_client.search.return_value = [hit]

        results = await provider.search_points(
            collection_name="col_test",
            query_vector=[0.1, 0.2],
            filter_conditions={},
        )

        assert len(results) == 1
        assert set(results[0].keys()) == {"point_id", "score", "payload"}
        assert "vector" not in results[0]

    async def test_search_points_preserves_default_arguments(
        self, provider: QdrantVectorDBProvider, mock_qdrant_client: AsyncMock
    ) -> None:
        """Verify default limit=50 and offset=None preserve with_vectors=False."""
        mock_qdrant_client.search.return_value = []

        results = await provider.search_points(
            collection_name="col_default",
            query_vector=[0.0, 1.0],
            filter_conditions={},
        )

        assert results == []
        _, kwargs = mock_qdrant_client.search.call_args
        assert kwargs["limit"] == 50
        assert kwargs["offset"] is None
        assert kwargs["query_filter"] is None
        assert kwargs["with_vectors"] is False
        assert kwargs["with_payload"] is True
