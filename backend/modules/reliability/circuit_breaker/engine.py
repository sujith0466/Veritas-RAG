"""Circuit Breaker Engine (`ADR-005`, `Phase 2 Milestone 5`).

Redis-backed distributed circuit breaker managing target service health states
and controlling failover to degraded fallback paths.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from redis.asyncio import Redis

from backend.cache.client import get_redis_client
from backend.modules.reliability.circuit_breaker.states import CircuitState
from backend.modules.reliability.schemas.reliability_dto import \
    CircuitBreakerStateDTO

logger = structlog.get_logger(__name__)


class CircuitBreakerEngine:
    """Distributed Redis state machine for target service health and failover protection."""

    def __init__(
        self,
        redis_client: Redis[Any] | None = None,
        failure_threshold: int = 5,
        recovery_threshold: int = 3,
        cooldown_seconds: int = 30,
    ) -> None:
        self._redis = redis_client
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.cooldown_seconds = cooldown_seconds

    @property
    def redis(self) -> Redis[Any]:
        """Return the injected Redis client or resolve singleton."""
        if self._redis is None:
            self._redis = get_redis_client()
        return self._redis

    def _state_key(self, tenant_id: str, target: str) -> str:
        return f"{tenant_id}:circuit_breaker:{target}:state"

    def _cooldown_key(self, tenant_id: str, target: str) -> str:
        return f"{tenant_id}:circuit_breaker:{target}:cooldown"

    def _failures_key(self, tenant_id: str, target: str) -> str:
        return f"{tenant_id}:circuit_breaker:{target}:failures"

    def _probes_key(self, tenant_id: str, target: str) -> str:
        return f"{tenant_id}:circuit_breaker:{target}:probes"

    def _last_ts_key(self, tenant_id: str, target: str) -> str:
        return f"{tenant_id}:circuit_breaker:{target}:last_ts"

    async def check_state(self, tenant_id: str, target: str) -> CircuitState:
        """Check current circuit breaker state, automatically decaying OPEN to HALF_OPEN when cooldown expires."""
        state_key = self._state_key(tenant_id, target)
        state_val = await self.redis.get(state_key)

        if state_val == CircuitState.OPEN.value:
            cooldown_key = self._cooldown_key(tenant_id, target)
            cooldown = await self.redis.get(cooldown_key)
            if cooldown is None:
                # Cooldown period expired -> transition to HALF_OPEN
                await self.redis.set(state_key, CircuitState.HALF_OPEN.value)
                await self.redis.delete(self._probes_key(tenant_id, target))
                logger.info(
                    "Circuit breaker cooldown expired; transitioned to HALF_OPEN",
                    tenant_id=tenant_id,
                    target=target,
                )
                return CircuitState.HALF_OPEN
            return CircuitState.OPEN

        if state_val == CircuitState.HALF_OPEN.value:
            return CircuitState.HALF_OPEN

        return CircuitState.CLOSED

    async def record_failure(
        self, tenant_id: str, target: str, error_code: str
    ) -> CircuitState:
        """Record a target failure. May trip circuit from CLOSED to OPEN or re-trip from HALF_OPEN."""
        current_state = await self.check_state(tenant_id, target)
        state_key = self._state_key(tenant_id, target)
        cooldown_key = self._cooldown_key(tenant_id, target)
        last_ts_key = self._last_ts_key(tenant_id, target)

        now = time.time()
        await self.redis.set(last_ts_key, str(now))

        if current_state == CircuitState.HALF_OPEN:
            await self.redis.set(state_key, CircuitState.OPEN.value)
            await self.redis.set(cooldown_key, "1", ex=self.cooldown_seconds)
            logger.warning(
                "Circuit breaker probe failed while HALF_OPEN; re-tripped to OPEN",
                tenant_id=tenant_id,
                target=target,
                error_code=error_code,
            )
            return CircuitState.OPEN

        if current_state == CircuitState.CLOSED:
            failures_key = self._failures_key(tenant_id, target)
            failures = await self.redis.incr(failures_key)
            if failures == 1:
                await self.redis.expire(failures_key, 60)  # 60-second sliding window

            if failures >= self.failure_threshold:
                await self.redis.set(state_key, CircuitState.OPEN.value)
                await self.redis.set(cooldown_key, "1", ex=self.cooldown_seconds)
                logger.warning(
                    "Circuit breaker tripped to OPEN due to threshold breach",
                    tenant_id=tenant_id,
                    target=target,
                    failures=failures,
                    threshold=self.failure_threshold,
                    error_code=error_code,
                )
                return CircuitState.OPEN

            return CircuitState.CLOSED

        return CircuitState.OPEN

    async def record_success(self, tenant_id: str, target: str) -> None:
        """Record a target success. Clears failures when CLOSED or increments probes when HALF_OPEN."""
        current_state = await self.check_state(tenant_id, target)
        state_key = self._state_key(tenant_id, target)

        if current_state == CircuitState.HALF_OPEN:
            probes_key = self._probes_key(tenant_id, target)
            probes = await self.redis.incr(probes_key)
            if probes >= self.recovery_threshold:
                await self.redis.set(state_key, CircuitState.CLOSED.value)
                await self.redis.delete(
                    self._failures_key(tenant_id, target),
                    self._probes_key(tenant_id, target),
                    self._cooldown_key(tenant_id, target),
                )
                logger.info(
                    "Circuit breaker recovered to CLOSED after successful probes",
                    tenant_id=tenant_id,
                    target=target,
                    probes=probes,
                )
        elif current_state == CircuitState.CLOSED:
            await self.redis.delete(
                self._failures_key(tenant_id, target),
                self._probes_key(tenant_id, target),
            )

    async def get_circuit_breaker_state(
        self, tenant_id: str, target: str
    ) -> CircuitBreakerStateDTO:
        """Fetch complete snapshot of target circuit breaker state and counters."""
        state = await self.check_state(tenant_id, target)
        failures_str = await self.redis.get(self._failures_key(tenant_id, target))
        failures = int(failures_str) if failures_str else 0

        last_ts_str = await self.redis.get(self._last_ts_key(tenant_id, target))
        last_ts = float(last_ts_str) if last_ts_str else None

        ttl = 0
        if state == CircuitState.OPEN:
            redis_ttl = await self.redis.ttl(self._cooldown_key(tenant_id, target))
            if redis_ttl and redis_ttl > 0:
                ttl = redis_ttl

        return CircuitBreakerStateDTO(
            tenant_id=tenant_id,
            target=target,
            state=state,
            failures=failures,
            last_failure_timestamp=last_ts,
            cooldown_ttl_seconds=ttl,
        )

    async def force_reset(self, tenant_id: str, target: str) -> bool:
        """Admin operation: immediately force circuit state to CLOSED and clear all error counters."""
        await self.redis.set(
            self._state_key(tenant_id, target), CircuitState.CLOSED.value
        )
        await self.redis.delete(
            self._failures_key(tenant_id, target),
            self._probes_key(tenant_id, target),
            self._cooldown_key(tenant_id, target),
            self._last_ts_key(tenant_id, target),
        )
        logger.info(
            "Circuit breaker force reset to CLOSED by administrator",
            tenant_id=tenant_id,
            target=target,
        )
        return True
