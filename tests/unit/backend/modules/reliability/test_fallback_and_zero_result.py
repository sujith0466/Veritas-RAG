"""Unit Tests for FallbackRouter & ZeroResultRecoverer (`ADR-005`, `Phase 2 Milestone 5`).

Tests sparse BM25 failover mapping, stopword stripping during zero-result recovery,
and uninitialized sparse index exception handling (`REL_004`, `REL_005`).
"""

from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from backend.modules.reliability.fallbacks.router import FallbackRouter
from backend.modules.reliability.fallbacks.zero_result import ZeroResultRecoverer
from backend.modules.reliability.schemas.errors import (
    FallbackProviderUnavailableError,
    ZeroResultRecoveryFailedError,
)
from backend.modules.retrieval.providers.sparse.bm25_provider import BM25SparseSearchProvider
from backend.modules.retrieval.schemas.errors import SparseIndexNotFoundError
from backend.modules.retrieval.schemas.retrieval_dto import CandidatePointDTO


@pytest.fixture
def mock_sparse_provider() -> AsyncMock:
    provider = AsyncMock(spec=BM25SparseSearchProvider)
    return provider


@pytest.mark.asyncio
async def test_fallback_router_success(mock_sparse_provider: AsyncMock) -> None:
    mock_sparse_provider.search_keywords.return_value = [
        CandidatePointDTO(
            chunk_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            document_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            document_version_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            tenant_id="tenant_1",
            content="Fallback content text",
            score=12.5,
            source="sparse",
            rank=1,
            metadata={"chapter": 1},
        )
    ]
    router = FallbackRouter(sparse_provider=mock_sparse_provider)

    result = await router.route_fallback(
        query="test query",
        tenant_id="tenant_1",
        reason="CircuitBreakerOpen",
        correlation_id="corr_123",
        limit=5,
    )

    assert result.is_degraded_fallback is True
    assert result.fallback_reason == "CircuitBreakerOpen"
    assert len(result.candidates) == 1
    assert result.candidates[0].is_fallback is True
    assert result.candidates[0].source == "fallback_bm25"
    assert result.candidates[0].content == "Fallback content text"


@pytest.mark.asyncio
async def test_fallback_router_uninitialized_index_raises_rel_004(mock_sparse_provider: AsyncMock) -> None:
    mock_sparse_provider.search_keywords.side_effect = SparseIndexNotFoundError("Index missing")
    router = FallbackRouter(sparse_provider=mock_sparse_provider)

    with pytest.raises(FallbackProviderUnavailableError) as exc_info:
        await router.route_fallback(
            query="test",
            tenant_id="tenant_missing",
            reason="Timeout",
            correlation_id="corr_456",
        )
    assert exc_info.value.code == "REL_004"


@pytest.mark.asyncio
async def test_zero_result_recoverer_broadening_success(mock_sparse_provider: AsyncMock) -> None:
    mock_sparse_provider.search_keywords.return_value = [
        CandidatePointDTO(
            chunk_id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
            document_id=uuid.UUID("55555555-5555-5555-5555-555555555555"),
            document_version_id=uuid.UUID("66666666-6666-6666-6666-666666666666"),
            tenant_id="tenant_1",
            content="Recovered broadened content",
            score=8.4,
            source="sparse",
            rank=1,
            metadata={},
        )
    ]
    recoverer = ZeroResultRecoverer(sparse_provider=mock_sparse_provider)

    # Query with stopwords: 'what is the circuit breaker' -> after stripping: 'circuit breaker'
    result = await recoverer.recover_empty_results(
        query="what is the circuit breaker",
        tenant_id="tenant_1",
        correlation_id="corr_789",
        limit=5,
    )

    assert result.is_zero_result_broadened is True
    assert result.is_degraded_fallback is False
    assert len(result.candidates) == 1
    assert result.candidates[0].is_broadened is True
    assert result.candidates[0].source == "zero_broadened"
    mock_sparse_provider.search_keywords.assert_called_once_with(
        tenant_id="tenant_1",
        query="circuit breaker",
        limit=5,
    )


@pytest.mark.asyncio
async def test_zero_result_recoverer_empty_after_broadening_raises_rel_005(mock_sparse_provider: AsyncMock) -> None:
    mock_sparse_provider.search_keywords.return_value = []
    recoverer = ZeroResultRecoverer(sparse_provider=mock_sparse_provider)

    with pytest.raises(ZeroResultRecoveryFailedError) as exc_info:
        await recoverer.recover_empty_results(
            query="unknown target term",
            tenant_id="tenant_1",
            correlation_id="corr_000",
        )
    assert exc_info.value.code == "REL_005"
