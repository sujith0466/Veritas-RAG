"""Hybrid Retrieval REST API routes (`/api/v1/retrieval`).

Provides endpoints for executing production hybrid search queries (`POST /search`),
inspecting comparative multi-stage results in developer sandbox (`POST /sandbox`),
and monitoring tenant KPIs and query audit history (`GET /metrics`, `GET /history`).
"""

from typing import Any
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from structlog import get_logger

from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.modules.retrieval.api.dependencies import (
    get_retrieval_orchestrator,
    get_retrieval_repository,
    resolve_tenant,
)
from backend.modules.retrieval.repositories.retrieval_repository import (
    RetrievalRepository,
)
from backend.modules.retrieval.schemas.errors import (
    CandidateDeduplicationError,
    InvalidQueryError,
    RerankerTimeoutError,
    RetrievalErrorCode,
    SparseIndexNotFoundError,
    VectorStoreUnavailableError,
)
from backend.modules.retrieval.schemas.retrieval_dto import (
    RetrievalMetricsDTO,
    RetrievalQueryLogDTO,
    RetrievalResultDTO,
    SearchRequestDTO,
    SearchSandboxResponseDTO,
)
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator

logger = get_logger(__name__)
router = APIRouter(prefix="/retrieval", tags=["Hybrid Retrieval Engine"])


def _build_metadata(request: Request) -> ResponseMetadata:
    req_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return ResponseMetadata(request_id=req_id)


def _handle_retrieval_exception(exc: Exception) -> None:
    from backend.core.exceptions.base import RAGuardException
    if isinstance(exc, RAGuardException):
        raise exc
    raise RetrievalDomainException(
        code=RetrievalErrorCode.RET_004,
        message=f"Internal retrieval error: {str(exc)}",
    ) from exc


@router.post(
    "/search",
    response_model=SuccessResponse[RetrievalResultDTO],
    status_code=status.HTTP_200_OK,
    summary="Execute multi-stage hybrid search query (Dense + Sparse + Rerank)",
)
async def execute_search(
    request_dto: SearchRequestDTO,
    request: Request,
    tenant_id: str = Depends(resolve_tenant),
    correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    orchestrator: RetrievalOrchestrator = Depends(get_retrieval_orchestrator),
) -> SuccessResponse[RetrievalResultDTO]:
    """Execute live multi-stage search with RRF fusion and cross-encoder reranking (`ADR-002`)."""
    corr_id = correlation_id or getattr(request.state, "correlation_id", str(uuid.uuid4()))
    try:
        result = await orchestrator.execute_hybrid_search(
            options=request_dto,
            tenant_id=tenant_id,
            correlation_id=corr_id,
        )
        return SuccessResponse[RetrievalResultDTO](
            data=result,
            metadata=_build_metadata(request),
        )
    except Exception as exc:
        logger.error("Error executing /search endpoint", error=str(exc))
        _handle_retrieval_exception(exc)


@router.post(
    "/sandbox",
    response_model=SuccessResponse[SearchSandboxResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Execute multi-stage comparative search for developers/sandbox UI",
)
async def execute_sandbox(
    request_dto: SearchRequestDTO,
    request: Request,
    tenant_id: str = Depends(resolve_tenant),
    correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    orchestrator: RetrievalOrchestrator = Depends(get_retrieval_orchestrator),
) -> SuccessResponse[SearchSandboxResponseDTO]:
    """Execute side-by-side search comparing raw dense, sparse, RRF, and reranked candidates (`ADR-005`)."""
    corr_id = correlation_id or getattr(request.state, "correlation_id", str(uuid.uuid4()))
    try:
        sandbox_res = await orchestrator.execute_sandbox_search(
            options=request_dto,
            tenant_id=tenant_id,
            correlation_id=corr_id,
        )
        return SuccessResponse[SearchSandboxResponseDTO](
            data=sandbox_res,
            metadata=_build_metadata(request),
        )
    except Exception as exc:
        logger.error("Error executing /sandbox endpoint", error=str(exc))
        _handle_retrieval_exception(exc)


@router.get(
    "/metrics",
    response_model=SuccessResponse[RetrievalMetricsDTO],
    status_code=status.HTTP_200_OK,
    summary="Retrieve tenant search KPIs and stage latency breakdowns",
)
async def get_metrics(
    request: Request,
    tenant_id: str = Depends(resolve_tenant),
    repo: RetrievalRepository = Depends(get_retrieval_repository),
) -> SuccessResponse[RetrievalMetricsDTO]:
    """Fetch aggregate KPIs including total queries, P95 latency, and average candidate densities."""
    try:
        metrics = await repo.get_tenant_metrics(tenant_id)
        return SuccessResponse[RetrievalMetricsDTO](
            data=metrics,
            metadata=_build_metadata(request),
        )
    except Exception as exc:
        logger.error("Error retrieving search metrics", error=str(exc))
        _handle_retrieval_exception(exc)


@router.get(
    "/history",
    response_model=SuccessResponse[list[RetrievalQueryLogDTO]],
    status_code=status.HTTP_200_OK,
    summary="Retrieve paginated retrieval query audit logs",
)
async def get_history(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant_id: str = Depends(resolve_tenant),
    repo: RetrievalRepository = Depends(get_retrieval_repository),
) -> SuccessResponse[list[RetrievalQueryLogDTO]]:
    """Fetch paginated search query execution logs for the active tenant namespace."""
    try:
        logs = await repo.get_query_history(tenant_id=tenant_id, limit=limit, offset=offset)
        dtos = [
            RetrievalQueryLogDTO(
                id=log.id,
                tenant_id=log.tenant_id,
                correlation_id=log.correlation_id,
                query_text=log.query_text,
                dense_candidate_count=log.dense_candidate_count,
                sparse_candidate_count=log.sparse_candidate_count,
                merged_unique_count=log.merged_unique_count,
                final_top_k=log.final_top_k,
                total_duration_ms=log.total_duration_ms,
                stage_breakdown_json=log.stage_breakdown_json if isinstance(log.stage_breakdown_json, dict) else {},
            )
            for log in logs
        ]
        return SuccessResponse[list[RetrievalQueryLogDTO]](
            data=dtos,
            metadata=_build_metadata(request),
        )
    except Exception as exc:
        logger.error("Error retrieving query history", error=str(exc))
        _handle_retrieval_exception(exc)
