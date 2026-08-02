"""Integration tests for Qdrant Foundation capabilities.

Tests CollectionNameBuilder, QdrantMetrics, and QdrantProvider abstraction.
"""

from typing import Any
import uuid

import pytest

from backend.infrastructure.vector_db.utils import CollectionNameBuilder
from backend.modules.vector.providers.qdrant_provider import QdrantVectorDBProvider
from backend.modules.vector.schemas.payload import (
    CollectionConfigDTO,
    VectorPointDTO,
)
from backend.vector_db.metrics import QdrantMetrics


@pytest.mark.asyncio
async def test_collection_name_builder():
    """Test strict tenant namespace building."""
    # Should lowercase and replace hyphens
    tenant_id = "TENANT-123-abc"
    collection_name = CollectionNameBuilder.build(tenant_id)
    assert collection_name == "raguard_tenant_123_abc"


@pytest.mark.asyncio
async def test_qdrant_metrics_singleton():
    """Test metrics telemetry increments and averages."""
    # Reset stats for clean test
    QdrantMetrics._searches = 0
    QdrantMetrics._search_latency = 0.0
    QdrantMetrics._upserts = 0
    QdrantMetrics._upsert_latency = 0.0
    QdrantMetrics._collection_creations = 0

    QdrantMetrics.record_collection_creation()
    QdrantMetrics.record_upsert(10.0)
    QdrantMetrics.record_upsert(20.0)
    QdrantMetrics.record_search(5.0)

    stats = QdrantMetrics.get_stats()

    assert stats["collection_creations"] == 1
    assert stats["upserts"] == 2
    assert stats["avg_upsert_latency_ms"] == 15.0
    assert stats["searches"] == 1
    assert stats["avg_search_latency_ms"] == 5.0


@pytest.mark.asyncio
async def test_qdrant_provider_interface(mocker: Any):
    """Test that the QdrantProvider correctly delegates to native gRPC methods."""
    # We mock the underlying AsyncQdrantClient to avoid needing a live Qdrant instance
    mock_client = mocker.AsyncMock()
    provider = QdrantVectorDBProvider(client=mock_client)

    tenant_id = str(uuid.uuid4())
    collection_name = CollectionNameBuilder.build(tenant_id)

    # 1. Ensure Collection
    config = CollectionConfigDTO(
        collection_name=collection_name,
        dimension=384,
        distance_metric="Cosine",
        scalar_quantization=True
    )

    mock_client.collection_exists.return_value = False
    await provider.ensure_collection(config)
    mock_client.create_collection.assert_called_once()

    # 2. Upsert Points
    point = VectorPointDTO(
        point_id=uuid.uuid4(),
        vector=[0.1] * 384,
        payload={
            "tenant_id": tenant_id,
            "document_id": "doc1",
            "document_version_id": "v1",
            "content_hash": "abc"
        }
    )
    await provider.upsert_points(collection_name, [point])
    mock_client.upsert.assert_called_once()

    # 3. Search Points
    # Mock search return value
    mock_hit = mocker.MagicMock()
    mock_hit.id = str(uuid.uuid4())
    mock_hit.score = 0.95
    mock_hit.payload = {"tenant_id": tenant_id}
    mock_client.search.return_value = [mock_hit]

    results = await provider.search_points(
        collection_name=collection_name,
        query_vector=[0.1] * 384,
        filter_conditions={"document_id": "doc1"},
        limit=5
    )

    mock_client.search.assert_called_once()
    assert len(results) == 1
    assert results[0]["score"] == 0.95
    assert results[0]["payload"]["tenant_id"] == tenant_id
