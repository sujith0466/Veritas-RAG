"""Reliability Module REST API Routes (`ADR-005`, `Phase 2 Milestone 5`).

Exposes endpoints for SLA-guarded reliable search, circuit breaker state monitoring
and admin force-reset, and tenant SLA summaries.
"""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, status

from backend.modules.reliability.api.dependencies import (
    get_reliability_gateway, get_reliability_repository)
from backend.modules.retrieval.api.dependencies import resolve_tenant
from backend.modules.reliability.repositories.reliability_repository import \
    ReliabilityRepository
from backend.modules.reliability.schemas.reliability_dto import (
    CircuitBreakerStateDTO, ReliableRetrievalResultDTO, SearchOptionsDTO,
    SLASummaryDTO)
from backend.modules.reliability.services.reliability_gateway import \
    ReliabilityGateway
from backend.modules.retrieval.schemas.errors import InvalidQueryError

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/reliability", tags=["Retrieval Reliability"])


@router.post(
    "/search",
    response_model=ReliableRetrievalResultDTO,
    status_code=status.HTTP_200_OK,
    summary="Execute SLA-guarded reliable search with circuit breaker and fallback failover",
)
async def execute_reliable_search_endpoint(
    options: SearchOptionsDTO,
    tenant_id: str = Depends(resolve_tenant),
    gateway: ReliabilityGateway = Depends(get_reliability_gateway),
) -> ReliableRetrievalResultDTO:
    """Execute hybrid search protected against timeouts and target failures."""
    if not options.query or not options.query.strip():
        raise InvalidQueryError("Search query must not be empty (`RET_001`).")

    return await gateway.execute_reliable_search(
        query=options.query.strip(),
        tenant_id=tenant_id,
        options=options,
    )


@router.get(
    "/circuit-breakers/{target}",
    response_model=CircuitBreakerStateDTO,
    status_code=status.HTTP_200_OK,
    summary="Fetch current health and error metrics for a target circuit breaker",
)
async def get_circuit_breaker_state_endpoint(
    target: str,
    tenant_id: str = Depends(resolve_tenant),
    gateway: ReliabilityGateway = Depends(get_reliability_gateway),
) -> CircuitBreakerStateDTO:
    """Retrieve circuit state, failure counters, and cooldown TTL."""
    return await gateway.get_circuit_breaker_state(tenant_id=tenant_id, target=target)


@router.post(
    "/circuit-breakers/{target}/reset",
    status_code=status.HTTP_200_OK,
    summary="Administrator operation to force reset a tripped circuit breaker back to CLOSED",
)
async def force_reset_circuit_breaker_endpoint(
    target: str,
    tenant_id: str = Depends(resolve_tenant),
    gateway: ReliabilityGateway = Depends(get_reliability_gateway),
) -> dict[str, Any]:
    """Force reset circuit state and clear failure windows."""
    success = await gateway.force_reset_circuit_breaker(
        tenant_id=tenant_id, target=target
    )
    return {"success": success, "target": target, "state": "CLOSED"}


@router.get(
    "/sla-summary",
    response_model=SLASummaryDTO,
    status_code=status.HTTP_200_OK,
    summary="Fetch tenant SLA compliance rates, fallback frequencies, and P95 latency",
)
async def get_sla_summary_endpoint(
    tenant_id: str = Depends(resolve_tenant),
    repository: ReliabilityRepository = Depends(get_reliability_repository),
) -> SLASummaryDTO:
    """Retrieve aggregate SLA metrics across recent tenant search queries."""
    return await repository.get_tenant_sla_summary(tenant_id)
