"""Unit tests for Phase 2 Milestone 4 (Hybrid Retrieval Engine) - Phase 4: REST API Routes."""

from unittest.mock import AsyncMock, MagicMock
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.main import create_app
from backend.modules.retrieval.api.dependencies import (
    get_retrieval_orchestrator,
    get_retrieval_repository,
    resolve_tenant,
)
from backend.modules.retrieval.schemas.errors import (
    InvalidQueryError,
    RerankerTimeoutError,
    SparseIndexNotFoundError,
)
from backend.modules.retrieval.schemas.retrieval_dto import (
    CandidatePointDTO,
    RankedEvidenceDTO,
    RetrievalMetricsDTO,
    RetrievalResultDTO,
    RetrievalStageBreakdownDTO,
    SearchSandboxResponseDTO,
)


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    orchestrator = MagicMock()
    chunk_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()

    evidence = RankedEvidenceDTO(
        chunk_id=chunk_id,
        document_id=doc_id,
        document_version_id=ver_id,
        tenant_id="org_api",
        content="Evidence chunk found via API search.",
        rrf_score=0.032,
        raw_rerank_score=0.95,
        final_rank=1,
    )

    breakdown = RetrievalStageBreakdownDTO(
        dense_ms=12.0,
        sparse_ms=10.0,
        rrf_fusion_ms=2.5,
        rerank_ms=28.0,
        total_ms=52.5,
    )

    orchestrator.execute_hybrid_search = AsyncMock(
        return_value=RetrievalResultDTO(
            query_text="API search query",
            tenant_id="org_api",
            correlation_id="corr_api_1",
            top_k_requested=5,
            dense_candidates_count=15,
            sparse_candidates_count=10,
            unique_candidates_merged=20,
            final_evidence=[evidence],
            stage_latencies=breakdown,
        )
    )

    orchestrator.execute_sandbox_search = AsyncMock(
        return_value=SearchSandboxResponseDTO(
            query_text="Sandbox API search",
            tenant_id="org_api",
            correlation_id="corr_api_2",
            dense_results=[
                CandidatePointDTO(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    document_version_id=ver_id,
                    tenant_id="org_api",
                    content="Dense match",
                    score=0.9,
                    source="dense",
                    rank=1,
                )
            ],
            sparse_results=[],
            rrf_merged_results=[],
            final_reranked_results=[evidence],
            stage_latencies=breakdown,
        )
    )
    return orchestrator


@pytest.fixture
def mock_repository() -> MagicMock:
    repo = MagicMock()
    repo.get_tenant_metrics = AsyncMock(
        return_value=RetrievalMetricsDTO(
            tenant_id="org_api",
            total_queries_executed=42,
            avg_total_duration_ms=65.4,
            p95_total_duration_ms=110.0,
        )
    )
    repo.get_query_history = AsyncMock(return_value=[])
    return repo


class TestRetrievalApiRoutes:
    def test_post_search_success(
        self, client: TestClient, app: FastAPI, mock_orchestrator: MagicMock
    ) -> None:
        app.dependency_overrides[resolve_tenant] = lambda: "org_api"
        app.dependency_overrides[get_retrieval_orchestrator] = lambda: mock_orchestrator
        try:
            response = client.post(
                "/api/v1/retrieval/search",
                json={"query": "API search query", "top_k": 5},
                headers={"X-Correlation-ID": "corr_api_1"},
            )
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["query_text"] == "API search query"
            assert data["tenant_id"] == "org_api"
            assert len(data["final_evidence"]) == 1
            assert data["final_evidence"][0]["raw_rerank_score"] == 0.95
        finally:
            app.dependency_overrides.clear()

    def test_post_search_invalid_query_returns_400(
        self, client: TestClient, app: FastAPI, mock_orchestrator: MagicMock
    ) -> None:
        mock_orchestrator.execute_hybrid_search.side_effect = InvalidQueryError(
            "Query empty (`RET_001`)"
        )
        app.dependency_overrides[resolve_tenant] = lambda: "org_api"
        app.dependency_overrides[get_retrieval_orchestrator] = lambda: mock_orchestrator
        try:
            response = client.post(
                "/api/v1/retrieval/search",
                json={"query": "   "},
            )
            assert response.status_code == 400
            assert response.json()["error"]["code"] == "RET_001"
        finally:
            app.dependency_overrides.clear()

    def test_post_search_sparse_index_not_found_returns_404(
        self, client: TestClient, app: FastAPI, mock_orchestrator: MagicMock
    ) -> None:
        mock_orchestrator.execute_hybrid_search.side_effect = SparseIndexNotFoundError(
            "Index missing (`RET_002`)"
        )
        app.dependency_overrides[resolve_tenant] = lambda: "org_api"
        app.dependency_overrides[get_retrieval_orchestrator] = lambda: mock_orchestrator
        try:
            response = client.post(
                "/api/v1/retrieval/search",
                json={"query": "Check index"},
            )
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "RET_002"
        finally:
            app.dependency_overrides.clear()

    def test_post_search_reranker_timeout_returns_503(
        self, client: TestClient, app: FastAPI, mock_orchestrator: MagicMock
    ) -> None:
        mock_orchestrator.execute_hybrid_search.side_effect = RerankerTimeoutError(
            "Cohere timeout (`RET_003`)"
        )
        app.dependency_overrides[resolve_tenant] = lambda: "org_api"
        app.dependency_overrides[get_retrieval_orchestrator] = lambda: mock_orchestrator
        try:
            response = client.post(
                "/api/v1/retrieval/search",
                json={"query": "Timeout query"},
            )
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "RET_003"
        finally:
            app.dependency_overrides.clear()

    def test_post_sandbox_success(
        self, client: TestClient, app: FastAPI, mock_orchestrator: MagicMock
    ) -> None:
        app.dependency_overrides[resolve_tenant] = lambda: "org_api"
        app.dependency_overrides[get_retrieval_orchestrator] = lambda: mock_orchestrator
        try:
            response = client.post(
                "/api/v1/retrieval/sandbox",
                json={"query": "Sandbox API search", "top_k": 10},
            )
            assert response.status_code == 200
            data = response.json()["data"]
            assert len(data["dense_results"]) == 1
            assert len(data["final_reranked_results"]) == 1
            assert data["stage_latencies"]["total_ms"] == 52.5
        finally:
            app.dependency_overrides.clear()

    def test_get_metrics_success(
        self, client: TestClient, app: FastAPI, mock_repository: MagicMock
    ) -> None:
        app.dependency_overrides[resolve_tenant] = lambda: "org_api"
        app.dependency_overrides[get_retrieval_repository] = lambda: mock_repository
        try:
            response = client.get(
                "/api/v1/retrieval/metrics"
            )
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["total_queries_executed"] == 42
            assert data["p95_total_duration_ms"] == 110.0
        finally:
            app.dependency_overrides.clear()

    def test_get_history_success(
        self, client: TestClient, app: FastAPI, mock_repository: MagicMock
    ) -> None:
        app.dependency_overrides[resolve_tenant] = lambda: "org_api"
        app.dependency_overrides[get_retrieval_repository] = lambda: mock_repository
        try:
            response = client.get(
                "/api/v1/retrieval/history?limit=10&offset=0"
            )
            assert response.status_code == 200
            assert isinstance(response.json()["data"], list)
        finally:
            app.dependency_overrides.clear()
