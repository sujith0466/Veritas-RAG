"""LLM Provider Manager (`WP-3C Phase 1`).

Implements the LLMProvider interface and acts as an automated failover router.
Integrates CircuitBreakerEngine for fast-fail when provider circuits are OPEN,
single-canary probe exclusivity when HALF_OPEN (SET NX EX 15), and zero provider
stitching on mid-stream failure (chunks_yielded > 0).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC
import time
from typing import Any
import uuid

import structlog

from backend.ai.interfaces.llm_provider import LLMProvider, LLMRequest, LLMResponse
from backend.ai.registry import ProviderRegistry
from backend.core.config import get_settings
from backend.core.exceptions import LLMProviderException
from backend.modules.reliability.circuit_breaker.engine import (
    CircuitBreakerEngine,
)
from backend.modules.reliability.circuit_breaker.states import CircuitState

logger = structlog.get_logger(__name__)

# Lightweight in-memory health metrics
_health_metrics: dict[str, dict[str, int | float]] = {}


def _init_metrics(provider_name: str) -> None:
    if provider_name not in _health_metrics:
        _health_metrics[provider_name] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "consecutive_failures": 0,
            "rate_limit_events": 0,
            "timeout_events": 0,
            "total_latency_ms": 0.0,
        }


class LLMProviderManager(LLMProvider):
    """Orchestrates LLM calls with automatic failover across configured priority providers.

    Obtains providers exclusively from `ProviderRegistry` and ensures zero business logic
    changes when switching primary or fallback AI models.
    Integrates CircuitBreakerEngine for fast failover and canary exclusivity.
    """

    def __init__(
        self,
        circuit_breaker: CircuitBreakerEngine | None = None,
    ) -> None:
        self._settings = get_settings().ai
        self._cb_engine = circuit_breaker or CircuitBreakerEngine()

    @property
    def circuit_breaker(self) -> CircuitBreakerEngine:
        """Return the integrated circuit breaker engine."""
        return self._cb_engine

    def _is_retryable(self, exc: Exception) -> bool:
        """Determine if the exception is a transient error that should be retried."""
        if isinstance(exc, LLMProviderException):
            if exc.status_code in (429, 500, 502, 503, 504):
                return True
            if exc.status_code in (400, 401, 403):
                return False
        err_msg = str(exc).lower()
        if (
            "timeout" in err_msg
            or "connection reset" in err_msg
            or "network" in err_msg
            or "504" in err_msg
            or "502" in err_msg
            or "429" in err_msg
        ):
            return True
        return False

    def _record_metrics(
        self,
        provider_name: str,
        success: bool,
        latency: float,
        exc: Exception | None = None,
    ) -> None:
        _init_metrics(provider_name)
        m = _health_metrics[provider_name]
        m["total_requests"] += 1
        m["total_latency_ms"] += latency
        if success:
            m["successful_requests"] += 1
            m["consecutive_failures"] = 0
        else:
            m["failed_requests"] += 1
            m["consecutive_failures"] += 1
            if exc:
                if (
                    isinstance(exc, LLMProviderException)
                    and exc.status_code == 429
                ):
                    m["rate_limit_events"] += 1
                elif "timeout" in str(exc).lower() or (
                    isinstance(exc, LLMProviderException)
                    and exc.status_code == 504
                ):
                    m["timeout_events"] += 1

    async def get_provider_circuit_states(self) -> dict[str, str]:
        """Query circuit breaker states for all configured providers in the priority list."""
        priority_list = self._settings.priority_list or []
        states: dict[str, str] = {}
        for p in priority_list:
            state = await self._cb_engine.check_state("system", p)
            states[p] = state.value
        return states

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Execute generate request across priority providers until one succeeds."""
        priority_list = self._settings.priority_list
        if not priority_list:
            raise LLMProviderException(
                message="No LLM providers configured in priority list.",
                detail={"priority_list": priority_list},
            )

        errors: list[dict[str, Any]] = []

        max_retries = getattr(self._settings, "max_retries", 3)
        initial_delay = getattr(self._settings, "retry_initial_delay", 1.0)

        for provider_name in priority_list:
            # 1. Circuit Breaker Check
            cb_state = await self._cb_engine.check_state("system", provider_name)
            if cb_state == CircuitState.OPEN:
                logger.info(
                    "Fast-failing generate request: provider circuit breaker is OPEN",
                    provider=provider_name,
                )
                errors.append({
                    "provider": provider_name,
                    "error": "Circuit Breaker OPEN",
                    "status_code": 503,
                })
                continue

            canary_token: str | None = None
            if cb_state == CircuitState.HALF_OPEN:
                canary_token = f"canary_gen_{uuid.uuid4().hex[:8]}"
                has_canary_lock = await self._cb_engine.acquire_canary_lock(
                    provider_name, canary_token, ttl_seconds=15
                )
                if not has_canary_lock:
                    logger.info(
                        "Skipping HALF_OPEN provider: concurrent canary probe already active",
                        provider=provider_name,
                    )
                    errors.append({
                        "provider": provider_name,
                        "error": "HALF_OPEN canary probe already active",
                        "status_code": 503,
                    })
                    continue

            try:
                provider = ProviderRegistry.get_provider(provider_name)
            except Exception as exc:
                if canary_token:
                    await self._cb_engine.release_canary_lock(
                        provider_name, canary_token
                    )
                logger.warning(
                    "Failed to instantiate provider from registry during generate",
                    provider=provider_name,
                    error=str(exc),
                )
                errors.append({"provider": provider_name, "error": str(exc)})
                continue

            # Retry Loop
            provider_succeeded = False
            for attempt in range(max_retries + 1):
                start_time = time.monotonic()
                try:
                    logger.debug(
                        "Attempting LLM generate",
                        provider=provider_name,
                        attempt=attempt,
                    )
                    response = await provider.generate(request)
                    latency = (time.monotonic() - start_time) * 1000

                    self._record_metrics(provider_name, success=True, latency=latency)
                    await self._cb_engine.record_success("system", provider_name)
                    if canary_token:
                        await self._cb_engine.release_canary_lock(
                            provider_name, canary_token
                        )
                        canary_token = None

                    logger.info(
                        "LLM Provider Generate Success",
                        provider=provider_name,
                        model=response.model_used,
                        latency_ms=round(latency, 2),
                        retry_count=attempt,
                        fallback_triggered=bool(errors),
                        final_provider=provider_name,
                    )

                    from datetime import datetime

                    from backend.modules.generation.services.llm_audit_service import (
                        LLMAuditService,
                    )

                    end_time = datetime.now(UTC)
                    start_time_dt = datetime.fromtimestamp(start_time, tz=UTC)
                    asyncio.create_task(
                        LLMAuditService.log_telemetry(
                            correlation_id=None,
                            provider=provider_name,
                            model=response.model_used,
                            mode="generate",
                            status="SUCCESS",
                            prompt_text=request.prompt,
                            system_prompt_text=request.system_instruction,
                            prompt_timestamp=start_time_dt,
                            response_timestamp=end_time,
                            raw_response_text=response.content,
                            final_response_text=response.content,
                            input_tokens=response.input_tokens,
                            output_tokens=response.output_tokens,
                            total_tokens=response.total_tokens,
                            latency_ms=latency,
                            error_message=None,
                            metadata_payload={
                                "attempt": attempt,
                                **(response.metadata or {}),
                            },
                        )
                    )

                    provider_succeeded = True
                    return response
                except Exception as exc:
                    latency = (time.monotonic() - start_time) * 1000
                    self._record_metrics(
                        provider_name, success=False, latency=latency, exc=exc
                    )

                    status_code = (
                        exc.status_code if hasattr(exc, "status_code") else None
                    )

                    logger.warning(
                        "LLM Provider Generate Failure",
                        provider=provider_name,
                        latency_ms=round(latency, 2),
                        retry_count=attempt,
                        failure_reason=str(exc),
                        status_code=status_code,
                    )

                    if attempt < max_retries and self._is_retryable(exc):
                        delay = initial_delay * (2**attempt)
                        logger.info(
                            "Retrying transient LLM error",
                            provider=provider_name,
                            delay=delay,
                            attempt=attempt + 1,
                        )
                        await asyncio.sleep(delay)
                    else:
                        await self._cb_engine.record_failure(
                            "system", provider_name, str(status_code or exc)
                        )
                        if canary_token:
                            await self._cb_engine.release_canary_lock(
                                provider_name, canary_token
                            )
                            canary_token = None

                        errors.append({
                            "provider": provider_name,
                            "error": str(exc),
                            "status_code": status_code,
                        })

                        from datetime import datetime

                        from backend.modules.generation.services.llm_audit_service import (
                            LLMAuditService,
                        )

                        end_time = datetime.now(UTC)
                        start_time_dt = datetime.fromtimestamp(start_time, tz=UTC)
                        asyncio.create_task(
                            LLMAuditService.log_telemetry(
                                correlation_id=None,
                                provider=provider_name,
                                model=None,
                                mode="generate",
                                status="ERROR",
                                prompt_text=request.prompt,
                                system_prompt_text=request.system_instruction,
                                prompt_timestamp=start_time_dt,
                                response_timestamp=end_time,
                                raw_response_text=None,
                                final_response_text=None,
                                input_tokens=None,
                                output_tokens=None,
                                total_tokens=None,
                                latency_ms=latency,
                                error_message=str(exc),
                                metadata_payload={
                                    "attempt": attempt,
                                    "status_code": status_code,
                                },
                            )
                        )
                        break

            if canary_token:
                await self._cb_engine.release_canary_lock(
                    provider_name, canary_token
                )

        logger.error(
            "All configured LLM providers failed for generate request",
            errors=errors,
        )
        raise LLMProviderException(
            message=f"All configured LLM providers failed: {[e['provider'] + ': ' + e['error'] for e in errors]}",
            detail={"errors": errors, "attempted_providers": priority_list},
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream tokens across priority providers with automatic failover on pre-stream init failure.

        If chunks have already been emitted (chunks_yielded > 0), the stream cannot be failed
        over cleanly; zero provider stitching is enforced and an LLMProviderException is raised.
        """
        priority_list = self._settings.priority_list
        if not priority_list:
            raise LLMProviderException(
                message="No LLM providers configured in priority list for streaming.",
                detail={"priority_list": priority_list},
            )

        errors: list[dict[str, Any]] = []
        max_retries = getattr(self._settings, "max_retries", 3)
        initial_delay = getattr(self._settings, "retry_initial_delay", 1.0)

        for provider_name in priority_list:
            # 1. Circuit Breaker Check
            cb_state = await self._cb_engine.check_state("system", provider_name)
            if cb_state == CircuitState.OPEN:
                logger.info(
                    "Fast-failing stream request: provider circuit breaker is OPEN",
                    provider=provider_name,
                )
                errors.append({
                    "provider": provider_name,
                    "error": "Circuit Breaker OPEN",
                    "status_code": 503,
                })
                continue

            canary_token: str | None = None
            if cb_state == CircuitState.HALF_OPEN:
                canary_token = f"canary_str_{uuid.uuid4().hex[:8]}"
                has_canary_lock = await self._cb_engine.acquire_canary_lock(
                    provider_name, canary_token, ttl_seconds=15
                )
                if not has_canary_lock:
                    logger.info(
                        "Skipping HALF_OPEN streaming provider: concurrent canary probe active",
                        provider=provider_name,
                    )
                    errors.append({
                        "provider": provider_name,
                        "error": "HALF_OPEN canary probe already active",
                        "status_code": 503,
                    })
                    continue

            try:
                provider = ProviderRegistry.get_provider(provider_name)
            except Exception as exc:
                if canary_token:
                    await self._cb_engine.release_canary_lock(
                        provider_name, canary_token
                    )
                logger.warning(
                    "Failed to instantiate provider from registry during stream",
                    provider=provider_name,
                    error=str(exc),
                )
                errors.append({"provider": provider_name, "error": str(exc)})
                continue

            # Retry Loop
            for attempt in range(max_retries + 1):
                chunks_yielded = 0
                start_time = time.monotonic()
                try:
                    logger.debug(
                        "Attempting LLM stream",
                        provider=provider_name,
                        attempt=attempt,
                    )

                    async for chunk in provider.stream(request):
                        chunks_yielded += 1
                        yield chunk

                    latency = (time.monotonic() - start_time) * 1000
                    self._record_metrics(provider_name, success=True, latency=latency)
                    await self._cb_engine.record_success("system", provider_name)
                    if canary_token:
                        await self._cb_engine.release_canary_lock(
                            provider_name, canary_token
                        )
                        canary_token = None

                    logger.info(
                        "LLM Provider Stream Success",
                        provider=provider_name,
                        latency_ms=round(latency, 2),
                        retry_count=attempt,
                        fallback_triggered=bool(errors),
                        final_provider=provider_name,
                    )
                    return
                except Exception as exc:
                    latency = (time.monotonic() - start_time) * 1000
                    status_code = (
                        exc.status_code if hasattr(exc, "status_code") else None
                    )

                    if chunks_yielded > 0:
                        # MID-STREAM ABORT: Enforce zero provider stitching!
                        self._record_metrics(
                            provider_name, success=False, latency=latency, exc=exc
                        )
                        await self._cb_engine.record_failure(
                            "system", provider_name, str(status_code or exc)
                        )
                        if canary_token:
                            await self._cb_engine.release_canary_lock(
                                provider_name, canary_token
                            )
                            canary_token = None

                        logger.error(
                            "Provider stream failed after emitting chunks; zero provider stitching enforced",
                            failed_provider=provider_name,
                            chunks_yielded=chunks_yielded,
                            error=str(exc),
                            latency_ms=round(latency, 2),
                            status_code=status_code,
                        )
                        raise LLMProviderException(
                            message=f"Stream aborted mid-generation from {provider_name}: {exc}",
                            detail={
                                "failed_provider": provider_name,
                                "chunks_yielded": chunks_yielded,
                                "is_interrupted": True,
                            },
                            status_code=status_code,
                        ) from exc

                    # PRE-STREAM FAILURE: chunks_yielded == 0
                    self._record_metrics(
                        provider_name, success=False, latency=latency, exc=exc
                    )
                    logger.warning(
                        "LLM Provider Stream Pre-Stream Failure",
                        provider=provider_name,
                        latency_ms=round(latency, 2),
                        retry_count=attempt,
                        failure_reason=str(exc),
                        status_code=status_code,
                    )

                    if attempt < max_retries and self._is_retryable(exc):
                        delay = initial_delay * (2**attempt)
                        logger.info(
                            "Retrying transient LLM stream error",
                            provider=provider_name,
                            delay=delay,
                            attempt=attempt + 1,
                        )
                        await asyncio.sleep(delay)
                    else:
                        await self._cb_engine.record_failure(
                            "system", provider_name, str(status_code or exc)
                        )
                        if canary_token:
                            await self._cb_engine.release_canary_lock(
                                provider_name, canary_token
                            )
                            canary_token = None

                        errors.append({
                            "provider": provider_name,
                            "error": str(exc),
                            "status_code": status_code,
                        })
                        break

            if canary_token:
                await self._cb_engine.release_canary_lock(
                    provider_name, canary_token
                )

        logger.error(
            "All configured LLM providers failed for stream request",
            errors=errors,
        )
        raise LLMProviderException(
            message=f"All configured LLM providers failed for streaming: {[e['provider'] + ': ' + e['error'] for e in errors]}",
            detail={"errors": errors, "attempted_providers": priority_list},
        )

    async def health_check(self) -> bool:
        """Verify that at least one provider in the priority list is healthy and not blocked by an OPEN circuit breaker."""
        priority_list = self._settings.priority_list
        for provider_name in priority_list:
            cb_state = await self._cb_engine.check_state("system", provider_name)
            if cb_state == CircuitState.OPEN:
                continue
            try:
                provider = ProviderRegistry.get_provider(provider_name)
                if await provider.health_check():
                    return True
            except Exception as exc:
                logger.debug(
                    "Provider health check failed or registry error",
                    provider=provider_name,
                    error=str(exc),
                )
        return False

    async def detailed_health_check(self) -> dict[str, Any]:
        """Perform health checks and return detailed runtime metrics including circuit breaker states."""
        results: dict[str, Any] = {}
        for provider_name in self._settings.priority_list:
            try:
                provider = ProviderRegistry.get_provider(provider_name)
                is_healthy = await provider.health_check()
                cb_state = await self._cb_engine.check_state("system", provider_name)

                metrics = _health_metrics.get(provider_name, {})
                success_rate = 0.0
                avg_response_time = 0.0
                total = metrics.get("total_requests", 0)
                if total > 0:
                    success_rate = metrics.get("successful_requests", 0) / float(total)
                    avg_response_time = metrics.get("total_latency_ms", 0.0) / float(total)

                results[provider_name] = {
                    "is_healthy": is_healthy and cb_state != CircuitState.OPEN,
                    "circuit_breaker_state": cb_state.value,
                    "total_requests": total,
                    "successful_requests": metrics.get("successful_requests", 0),
                    "failed_requests": metrics.get("failed_requests", 0),
                    "success_rate": round(success_rate, 2),
                    "failure_rate": round(1.0 - success_rate, 2) if total > 0 else 0.0,
                    "avg_response_time_ms": round(avg_response_time, 2),
                    "consecutive_failures": metrics.get("consecutive_failures", 0),
                    "rate_limit_events": metrics.get("rate_limit_events", 0),
                    "timeout_events": metrics.get("timeout_events", 0),
                }
            except Exception:
                results[provider_name] = {
                    "is_healthy": False,
                    "circuit_breaker_state": CircuitState.OPEN.value,
                }
        return results
