"""Reliability API Dependencies (`ADR-005`, `Phase 2 Milestone 5`).

FastAPI dependencies for resolving `ReliabilityGateway`, repositories,
and circuit breaker engines.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies.database import get_db
from backend.core.events.dispatcher import get_dispatcher
from backend.modules.reliability.circuit_breaker.engine import CircuitBreakerEngine
from backend.modules.reliability.fallbacks.router import FallbackRouter
from backend.modules.reliability.fallbacks.zero_result import ZeroResultRecoverer
from backend.modules.reliability.repositories.reliability_repository import ReliabilityRepository
from backend.modules.reliability.services.reliability_gateway import ReliabilityGateway
from backend.modules.retrieval.api.dependencies import _bm25_provider, get_retrieval_orchestrator
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator

_circuit_breaker = CircuitBreakerEngine()
_fallback_router = FallbackRouter(sparse_provider=_bm25_provider)
_zero_recoverer = ZeroResultRecoverer(sparse_provider=_bm25_provider)


def get_reliability_repository(
    session: AsyncSession = Depends(get_db),
) -> ReliabilityRepository:
    """Inject a `ReliabilityRepository` bound to the current transaction session."""
    return ReliabilityRepository(session)


def get_circuit_breaker_engine() -> CircuitBreakerEngine:
    """Inject the shared `CircuitBreakerEngine` instance."""
    return _circuit_breaker


def get_reliability_gateway(
    orchestrator: RetrievalOrchestrator = Depends(get_retrieval_orchestrator),
    repository: ReliabilityRepository = Depends(get_reliability_repository),
) -> ReliabilityGateway:
    """Inject the primary `ReliabilityGateway` wrapped around the hybrid retrieval orchestrator."""
    return ReliabilityGateway(
        orchestrator=orchestrator,
        circuit_breaker=_circuit_breaker,
        fallback_router=_fallback_router,
        zero_result_recoverer=_zero_recoverer,
        repository=repository,
        event_dispatcher=get_dispatcher(),
        target_module="qdrant_hybrid",
    )
