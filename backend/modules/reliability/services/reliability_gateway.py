"""Reliability Gateway (`ADR-005`, `Phase 2 Milestone 5`).

Wraps the primary Hybrid Retrieval Engine (`RetrievalOrchestrator`), providing:
- Circuit breaker state verification and trip handling (`REL_001`, `REL_003`)
- Degraded failover routing to sparse BM25 (`FallbackRouter`)
- Zero-result recovery broadening (`ZeroResultRecoverer`)
- SLA compliance monitoring and audit logging (`RetrievalSLALog`)
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import uuid4

import structlog

from backend.modules.reliability.circuit_breaker.engine import \
    CircuitBreakerEngine
from backend.modules.reliability.circuit_breaker.states import CircuitState
from backend.modules.reliability.events.payloads import (
    create_circuit_tripped_event, create_fallback_triggered_event)
from backend.modules.reliability.fallbacks.router import FallbackRouter
from backend.modules.reliability.fallbacks.zero_result import \
    ZeroResultRecoverer
from backend.modules.reliability.models.circuit_event import \
    CircuitBreakerEventLog
from backend.modules.reliability.models.sla_log import RetrievalSLALog
from backend.modules.reliability.repositories.reliability_repository import \
    ReliabilityRepository
from backend.modules.reliability.schemas.errors import CircuitBreakerOpenError
from backend.modules.reliability.schemas.reliability_dto import (
    CircuitBreakerStateDTO, ReliableCandidateDTO, ReliableRetrievalResultDTO,
    SearchOptionsDTO)
from backend.modules.retrieval.schemas.retrieval_dto import SearchRequestDTO
from backend.modules.retrieval.services.retrieval_service import \
    RetrievalOrchestrator

logger = structlog.get_logger(__name__)


class ReliabilityGateway:
    """Primary entry point for SLA-bounded, fault-tolerant retrieval across all tenants."""

    def __init__(
        self,
        orchestrator: RetrievalOrchestrator,
        circuit_breaker: CircuitBreakerEngine,
        fallback_router: FallbackRouter,
        zero_result_recoverer: ZeroResultRecoverer,
        repository: ReliabilityRepository | None = None,
        event_dispatcher: Any | None = None,
        target_module: str = "qdrant_hybrid",
    ) -> None:
        self.orchestrator = orchestrator
        self.circuit_breaker = circuit_breaker
        self.fallback_router = fallback_router
        self.zero_result_recoverer = zero_result_recoverer
        self.repository = repository
        self.event_dispatcher = event_dispatcher
        self.target_module = target_module

    async def execute_reliable_search(
        self,
        query: str,
        tenant_id: str,
        options: SearchOptionsDTO,
        correlation_id: str = "auto",
    ) -> ReliableRetrievalResultDTO:
        """Execute search protected by circuit breaker, timeout budget, and fallback failover."""
        start_time = time.perf_counter()
        if correlation_id == "auto" or not correlation_id:
            correlation_id = f"req_{uuid4().hex[:8]}"

        import sys

        from backend.observability.metrics import (record_query_metric,
                                                   record_stage_duration)
        from backend.observability.tracing import trace_query_processing

        span_ctx = trace_query_processing(
            correlation_id=correlation_id, tenant_id=tenant_id
        )
        span_ctx.__enter__()
        try:
            result = await self._execute_reliable_search_inner(
                query, tenant_id, options, correlation_id, start_time
            )
            duration_sec = time.perf_counter() - start_time
            record_stage_duration("query_processing", duration_sec)
            record_query_metric(
                tenant_id,
                outcome="success" if not result.is_sla_breached else "degraded",
                duration_seconds=duration_sec,
            )
            return result
        except Exception:
            duration_sec = time.perf_counter() - start_time
            record_stage_duration("query_processing", duration_sec)
            record_query_metric(
                tenant_id, outcome="failed", duration_seconds=duration_sec
            )
            raise
        finally:
            span_ctx.__exit__(*sys.exc_info())

    async def _execute_reliable_search_inner(
        self,
        query: str,
        tenant_id: str,
        options: SearchOptionsDTO,
        correlation_id: str,
        start_time: float,
    ) -> ReliableRetrievalResultDTO:
        # 1. Check circuit breaker state
        state = await self.circuit_breaker.check_state(
            tenant_id=tenant_id, target=self.target_module
        )

        if state == CircuitState.OPEN:
            if not options.enable_fallback:
                logger.warning(
                    "Circuit breaker OPEN and fallback disabled; rejecting query",
                    tenant_id=tenant_id,
                    target=self.target_module,
                )
                raise CircuitBreakerOpenError(
                    tenant_id=tenant_id, target=self.target_module
                )

            result = await self.fallback_router.route_fallback(
                query=query,
                tenant_id=tenant_id,
                reason="CircuitBreakerOpen",
                correlation_id=correlation_id,
                limit=options.top_k,
            )
            await self._record_sla_log(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                query=query,
                duration_ms=result.duration_ms,
                is_breached=result.duration_ms > options.sla_budget_ms,
                is_degraded=True,
                reason="CircuitBreakerOpen",
            )
            await self._emit_fallback_event(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                query=query,
                reason="CircuitBreakerOpen",
                duration_ms=result.duration_ms,
            )
            return result

        # 2. Execute Primary Hybrid Search with SLA Timeout Guard
        m4_request = SearchRequestDTO(
            query=query,
            top_k=options.top_k,
            limit_dense=max(20, options.top_k * 2),
            limit_sparse=max(20, options.top_k * 2),
        )

        try:
            m4_result = await asyncio.wait_for(
                self.orchestrator.execute_hybrid_search(
                    options=m4_request,
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                ),
                timeout=options.sla_budget_ms / 1000.0,
            )
        except (TimeoutError, Exception) as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if isinstance(exc, TimeoutError):
                reason = (
                    f"Execution timeout ({options.sla_budget_ms}ms budget exceeded)"
                )
                error_code = "REL_002"
                logger.warning(
                    "Primary hybrid retrieval timed out; tripping/recording failure",
                    tenant_id=tenant_id,
                    duration_ms=duration_ms,
                    budget_ms=options.sla_budget_ms,
                )
            else:
                reason = f"Execution failure: {type(exc).__name__} ({exc})"
                error_code = getattr(exc, "code", "RET_004")
                logger.error(
                    "Primary hybrid retrieval raised exception; recording failure",
                    tenant_id=tenant_id,
                    error=str(exc),
                    exc_info=True,
                )

            # Record failure on circuit breaker
            new_state = await self.circuit_breaker.record_failure(
                tenant_id=tenant_id,
                target=self.target_module,
                error_code=error_code,
            )

            if new_state == CircuitState.OPEN:
                await self._record_circuit_event(
                    tenant_id=tenant_id,
                    previous_state=state.value,
                    new_state=CircuitState.OPEN.value,
                    reason=reason,
                    error_code=error_code,
                )
                await self._emit_circuit_tripped_event(
                    tenant_id=tenant_id,
                    target_module=self.target_module,
                    failures=self.circuit_breaker.failure_threshold,
                    error_code=error_code,
                )

            if not options.enable_fallback:
                raise

            fallback_result = await self.fallback_router.route_fallback(
                query=query,
                tenant_id=tenant_id,
                reason=reason,
                correlation_id=correlation_id,
                limit=options.top_k,
            )
            total_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            fallback_result.duration_ms = total_duration_ms
            fallback_result.fallback_reason = reason
            fallback_result.is_sla_breached = total_duration_ms > options.sla_budget_ms

            await self._record_sla_log(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                query=query,
                duration_ms=total_duration_ms,
                is_breached=fallback_result.is_sla_breached,
                is_degraded=True,
                reason=reason,
            )
            await self._emit_fallback_event(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                query=query,
                reason=reason,
                duration_ms=total_duration_ms,
            )
            return fallback_result

        # 3. Clean execution: Record success and evaluate zero-result or standard return
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        await self.circuit_breaker.record_success(
            tenant_id=tenant_id, target=self.target_module
        )

        if state == CircuitState.HALF_OPEN:
            current_state = await self.circuit_breaker.check_state(
                tenant_id=tenant_id, target=self.target_module
            )
            if current_state == CircuitState.CLOSED:
                await self._record_circuit_event(
                    tenant_id=tenant_id,
                    previous_state=CircuitState.HALF_OPEN.value,
                    new_state=CircuitState.CLOSED.value,
                    reason="Target fully recovered after successful probes",
                    error_code=None,
                )

        if not m4_result.final_evidence and options.enable_zero_result_recovery:
            logger.info(
                "Primary hybrid search returned 0 candidates; invoking zero-result recovery",
                tenant_id=tenant_id,
                query=query,
            )
            try:
                recovered_result = (
                    await self.zero_result_recoverer.recover_empty_results(
                        query=query,
                        tenant_id=tenant_id,
                        correlation_id=correlation_id,
                        limit=options.top_k,
                    )
                )
                total_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
                recovered_result.duration_ms = total_duration_ms
                recovered_result.is_sla_breached = (
                    total_duration_ms > options.sla_budget_ms
                )

                await self._record_sla_log(
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    query=query,
                    duration_ms=total_duration_ms,
                    is_breached=recovered_result.is_sla_breached,
                    is_degraded=False,
                    reason=None,
                )
                return recovered_result
            except Exception as exc:
                logger.warning(
                    "Zero-result recovery could not surface candidates; returning empty primary response",
                    tenant_id=tenant_id,
                    error=str(exc),
                )

        is_breached = duration_ms > options.sla_budget_ms
        candidates = [
            ReliableCandidateDTO(
                chunk_id=str(item.chunk_id),
                document_id=str(item.document_id),
                document_version_id=str(item.document_version_id),
                tenant_id=item.tenant_id,
                content=item.content,
                score=(
                    item.raw_rerank_score
                    if item.raw_rerank_score is not None
                    else item.rrf_score
                ),
                rank=item.final_rank,
                source="hybrid",
                is_fallback=False,
                is_broadened=False,
                metadata=item.metadata,
            )
            for item in m4_result.final_evidence
        ]

        result = ReliableRetrievalResultDTO(
            query_text=query,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            candidates=candidates,
            duration_ms=duration_ms,
            is_sla_breached=is_breached,
            is_degraded_fallback=False,
            fallback_reason=None,
            is_zero_result_broadened=False,
        )

        await self._record_sla_log(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            query=query,
            duration_ms=duration_ms,
            is_breached=is_breached,
            is_degraded=False,
            reason=None,
        )
        return result

    async def get_circuit_breaker_state(
        self, tenant_id: str, target: str | None = None
    ) -> CircuitBreakerStateDTO:
        """Fetch current state of target circuit breaker."""
        target_mod = target or self.target_module
        return await self.circuit_breaker.get_circuit_breaker_state(
            tenant_id=tenant_id, target=target_mod
        )

    async def force_reset_circuit_breaker(
        self, tenant_id: str, target: str | None = None
    ) -> bool:
        """Admin operation: force reset circuit breaker state."""
        target_mod = target or self.target_module
        return await self.circuit_breaker.force_reset(
            tenant_id=tenant_id, target=target_mod
        )

    async def _record_sla_log(
        self,
        tenant_id: str,
        correlation_id: str,
        query: str,
        duration_ms: float,
        is_breached: bool,
        is_degraded: bool,
        reason: str | None,
    ) -> None:
        if not self.repository:
            return
        try:
            log_entity = RetrievalSLALog(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                query_text=query,
                target_module=self.target_module,
                duration_ms=duration_ms,
                is_sla_breached=is_breached,
                is_degraded_fallback=is_degraded,
                fallback_reason=reason,
            )
            await self.repository.log_sla_metric(log_entity)
        except Exception as exc:
            logger.error(
                "Failed to persist retrieval SLA log to repository", error=str(exc)
            )

    async def _record_circuit_event(
        self,
        tenant_id: str,
        previous_state: str,
        new_state: str,
        reason: str,
        error_code: str | None,
    ) -> None:
        if not self.repository:
            return
        try:
            event_entity = CircuitBreakerEventLog(
                tenant_id=tenant_id,
                target_module=self.target_module,
                previous_state=previous_state,
                new_state=new_state,
                reason=reason,
                error_code=error_code,
            )
            await self.repository.log_circuit_event(event_entity)
        except Exception as exc:
            logger.error(
                "Failed to persist circuit breaker event log to repository",
                error=str(exc),
            )

    async def _emit_fallback_event(
        self,
        tenant_id: str,
        correlation_id: str,
        query: str,
        reason: str,
        duration_ms: float,
    ) -> None:
        if not self.event_dispatcher:
            return
        try:
            event = create_fallback_triggered_event(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                query_text=query,
                fallback_reason=reason,
                duration_ms=duration_ms,
            )
            await self.event_dispatcher.publish(event)
        except Exception as exc:
            logger.error(
                "Failed to emit retrieval.fallback_triggered event", error=str(exc)
            )

    async def _emit_circuit_tripped_event(
        self,
        tenant_id: str,
        target_module: str,
        failures: int,
        error_code: str | None,
    ) -> None:
        if not self.event_dispatcher:
            return
        try:
            event = create_circuit_tripped_event(
                tenant_id=tenant_id,
                target_module=target_module,
                failures=failures,
                error_code=error_code,
            )
            await self.event_dispatcher.publish(event)
        except Exception as exc:
            logger.error(
                "Failed to emit retrieval.circuit_breaker_tripped event", error=str(exc)
            )
