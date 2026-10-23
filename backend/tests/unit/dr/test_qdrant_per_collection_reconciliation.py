"""Unit tests for Qdrant Per-Collection Parity Verification (`WP-3C Phase 2`, `TSK-3C-07`, `Audit E`).

Verifies:
1. Dynamic collection dimension inspection (expected_dim == actual_dim).
2. Point-ID set equality (Tier I-A): detects missing and unexpected points.
3. Payload tenant isolation assertion (Tier I-B): detects cross-tenant points.
4. Vector float integrity checks (Tier II): asserts finite real numbers, detects NaN and Infinite values.
"""

from __future__ import annotations

import pytest

from scripts.dr.verify_restore import (
    QdrantParityError,
    verify_qdrant_collection_parity,
)


def test_qdrant_parity_success():
    points = [
        {
            "id": "point-1",
            "payload": {"tenant_id": "tenant-abc", "document_id": "doc-1"},
            "vector": [0.1, 0.2, 0.3],
        },
        {
            "id": "point-2",
            "payload": {"tenant_id": "tenant-abc", "document_id": "doc-1"},
            "vector": [0.4, 0.5, 0.6],
        },
    ]

    res = verify_qdrant_collection_parity(
        collection_name="test_col",
        expected_dim=3,
        expected_points=points,
        actual_points=points,
        actual_collection_dim=3,
    )
    assert res["status"] == "PARITY_CONFIRMED"
    assert res["verified_points"] == 2


def test_qdrant_parity_dimension_mismatch():
    with pytest.raises(QdrantParityError) as exc_info:
        verify_qdrant_collection_parity(
            collection_name="test_col",
            expected_dim=1536,
            expected_points=[],
            actual_points=[],
            actual_collection_dim=768,
        )
    assert "dimension mismatch" in str(exc_info.value)


def test_qdrant_parity_missing_points():
    expected = [{"id": "point-1", "payload": {}, "vector": [0.1]}, {"id": "point-2", "payload": {}, "vector": [0.2]}]
    actual = [{"id": "point-1", "payload": {}, "vector": [0.1]}]

    with pytest.raises(QdrantParityError) as exc_info:
        verify_qdrant_collection_parity(
            collection_name="test_col",
            expected_dim=1,
            expected_points=expected,
            actual_points=actual,
            actual_collection_dim=1,
        )
    assert "missing point IDs" in str(exc_info.value)


def test_qdrant_parity_cross_tenant_payload_mismatch():
    expected = [{"id": "point-1", "payload": {"tenant_id": "tenant-A"}, "vector": [0.1]}]
    actual = [{"id": "point-1", "payload": {"tenant_id": "tenant-B"}, "vector": [0.1]}]

    with pytest.raises(QdrantParityError) as exc_info:
        verify_qdrant_collection_parity(
            collection_name="test_col",
            expected_dim=1,
            expected_points=expected,
            actual_points=actual,
            actual_collection_dim=1,
        )
    assert "Cross-tenant payload mismatch" in str(exc_info.value)


def test_qdrant_parity_detects_nan_float():
    expected = [{"id": "point-1", "payload": {"tenant_id": "tenant-A"}, "vector": [0.1]}]
    actual = [{"id": "point-1", "payload": {"tenant_id": "tenant-A"}, "vector": [float("nan")]}]

    with pytest.raises(QdrantParityError) as exc_info:
        verify_qdrant_collection_parity(
            collection_name="test_col",
            expected_dim=1,
            expected_points=expected,
            actual_points=actual,
            actual_collection_dim=1,
        )
    assert "NaN or Infinite" in str(exc_info.value)
