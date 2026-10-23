"""Circuit Breaker Engine (`ADR-005`, `Phase 2 Milestone 5`, `WP-3C`).

Redis-backed distributed circuit breaker managing target service health states
and controlling failover to degraded fallback paths.
Supports dual-scope key migration (system vs tenant), owner-checked canary exclusivity
locks via Lua scripts, and fail-open degradation on Redis outages.
"""

from __future__ import annotations

import time
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError, RedisError
import structlog

from backend.cache.client import get_redis_client
from backend.modules.reliability.circuit_breaker.states import CircuitState
from backend.modules.reliability.schemas.reliability_dto import CircuitBreakerStateDTO

logger = structlog.get_logger(__name__)

# Known global AI provider targets that use system namespace
KNOWN_SYSTEM_PROVIDERS = {
    "openrouter",
    "gemini",
    "v1_engine",
    "mock",
    "ollama",
    "openai",
    "anthropic",
}

LUA_RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class CircuitBreakerEngine:
    """Distributed Redis state machine for target service health and failover protection."""

    def __init__(
        self,
        redis_client: Redis[Any] | None = None,
        failure_threshold: int = 5,
        recovery_threshold: int = 1,
        cooldown_seconds: int = 60,
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

    def is_system_target(self, tenant_id: str, target: str) -> bool:
        """Determine if target represents a global system service rather than a tenant-scoped module."""
        return tenant_id == "system" or target.lower() in KNOWN_SYSTEM_PROVIDERS

    def _state_key(self, tenant_id: str, target: str, force_tenant: bool = False) -> str:
        if not force_tenant and self.is_system_target(tenant_id, target):
            return f"system:circuit_breaker:{target}:state"
        return f"{tenant_id}:circuit_breaker:{target}:state"

    def _cooldown_key(self, tenant_id: str, target: str, force_tenant: bool = False) -> str:
        if not force_tenant and self.is_system_target(tenant_id, target):
            return f"system:circuit_breaker:{target}:cooldown"
        return f"{tenant_id}:circuit_breaker:{target}:cooldown"

    def _failures_key(self, tenant_id: str, target: str, force_tenant: bool = False) -> str:
        if not force_tenant and self.is_system_target(tenant_id, target):
            return f"system:circuit_breaker:{target}:failures"
        return f"{tenant_id}:circuit_breaker:{target}:failures"

    def _probes_key(self, tenant_id: str, target: str, force_tenant: bool = False) -> str:
        if not force_tenant and self.is_system_target(tenant_id, target):
            return f"system:circuit_breaker:{target}:probes"
        return f"{tenant_id}:circuit_breaker:{target}:probes"

    def _last_ts_key(self, tenant_id: str, target: str, force_tenant: bool = False) -> str:
        if not force_tenant and self.is_system_target(tenant_id, target):
            return f"system:circuit_breaker:{target}:last_ts"
        return f"{tenant_id}:circuit_breaker:{target}:last_ts"

    def _canary_lock_key(self, provider: str) -> str:
        return f"system:circuit_breaker:{provider}:canary_lock"

    async def check_state(self, tenant_id: str, target: str) -> CircuitState:
        """Check current circuit breaker state, automatically decaying OPEN to HALF_OPEN when cooldown expires.

        Implements Dual-Read with Precedence:
        Queries canonical 'system:circuit_breaker:{target}:state' first if target is a provider.
        If that key does not exist and tenant_id != 'system', falls back to '{tenant_id}:circuit_breaker:{target}:state'.
        On Redis failure, degrades fail-open to CircuitState.CLOSED.
        """
        try:
            state_key = self._state_key(tenant_id, target)
            state_val = await self.redis.get(state_key)

            # Dual-read fallback: if system key not present and tenant_id given, check legacy key
            if state_val is None and self.is_system_target(tenant_id, target) and tenant_id != "system":
                legacy_key = self._state_key(tenant_id, target, force_tenant=True)
                legacy_val = await self.redis.get(legacy_key)
                if legacy_val is not None:
                    state_val = legacy_val
                    state_key = legacy_key

            if state_val == CircuitState.OPEN.value:
                cooldown_key = (
                    self._cooldown_key(tenant_id, target, force_tenant=True)
                    if state_key.startswith(f"{tenant_id}:")
                    else self._cooldown_key(tenant_id, target)
                )
                cooldown = await self.redis.get(cooldown_key)
                if cooldown is None:
                    # Cooldown period expired -> transition to HALF_OPEN
                    await self.redis.set(state_key, CircuitState.HALF_OPEN.value)
                    probes_key = (
                        self._probes_key(tenant_id, target, force_tenant=True)
                        if state_key.startswith(f"{tenant_id}:")
                        else self._probes_key(tenant_id, target)
                    )
                    await self.redis.delete(probes_key)
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
        except (RedisConnectionError, RedisError, TimeoutError, OSError) as exc:
            logger.warning(
                "Redis unavailable during circuit breaker check_state; degrading fail-open",
                tenant_id=tenant_id,
                target=target,
                error=str(exc),
            )
            return CircuitState.CLOSED

    async def record_failure(
        self, tenant_id: str, target: str, error_code: str
    ) -> CircuitState:
        """Record a target failure. May trip circuit from CLOSED to OPEN or re-trip from HALF_OPEN.

        Implements Dual-Write:
        Writes to system:circuit_breaker:{target}:* and mirrors to {tenant_id}:circuit_breaker:{target}:*
        when tenant_id != 'system' for rolling rollout backward compatibility.
        Degrades fail-open on Redis errors.
        """
        try:
            current_state = await self.check_state(tenant_id, target)
            now = time.time()

            primary_state_key = self._state_key(tenant_id, target)
            primary_cooldown_key = self._cooldown_key(tenant_id, target)
            primary_last_ts_key = self._last_ts_key(tenant_id, target)
            primary_failures_key = self._failures_key(tenant_id, target)

            mirror_keys: list[tuple[str, str, str, str]] = []
            if self.is_system_target(tenant_id, target) and tenant_id != "system":
                mirror_keys.append((
                    self._state_key(tenant_id, target, force_tenant=True),
                    self._cooldown_key(tenant_id, target, force_tenant=True),
                    self._last_ts_key(tenant_id, target, force_tenant=True),
                    self._failures_key(tenant_id, target, force_tenant=True),
                ))

            await self.redis.set(primary_last_ts_key, str(now))
            for _, _, last_ts_k, _ in mirror_keys:
                await self.redis.set(last_ts_k, str(now))

            if current_state == CircuitState.HALF_OPEN:
                await self.redis.set(primary_state_key, CircuitState.OPEN.value)
                await self.redis.set(primary_cooldown_key, "1", ex=self.cooldown_seconds)
                for st_k, cd_k, _, _ in mirror_keys:
                    await self.redis.set(st_k, CircuitState.OPEN.value)
                    await self.redis.set(cd_k, "1", ex=self.cooldown_seconds)

                logger.warning(
                    "Circuit breaker probe failed while HALF_OPEN; re-tripped to OPEN",
                    tenant_id=tenant_id,
                    target=target,
                    error_code=error_code,
                )
                return CircuitState.OPEN

            if current_state == CircuitState.CLOSED:
                failures = await self.redis.incr(primary_failures_key)
                if failures == 1:
                    await self.redis.expire(primary_failures_key, self.cooldown_seconds)

                for _, _, _, fail_k in mirror_keys:
                    m_failures = await self.redis.incr(fail_k)
                    if m_failures == 1:
                        await self.redis.expire(fail_k, self.cooldown_seconds)

                if failures >= self.failure_threshold:
                    await self.redis.set(primary_state_key, CircuitState.OPEN.value)
                    await self.redis.set(primary_cooldown_key, "1", ex=self.cooldown_seconds)
                    for st_k, cd_k, _, _ in mirror_keys:
                        await self.redis.set(st_k, CircuitState.OPEN.value)
                        await self.redis.set(cd_k, "1", ex=self.cooldown_seconds)

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
        except (RedisConnectionError, RedisError, TimeoutError, OSError) as exc:
            logger.warning(
                "Redis unavailable during circuit breaker record_failure; degrading fail-open",
                tenant_id=tenant_id,
                target=target,
                error=str(exc),
            )
            return CircuitState.CLOSED

    async def record_success(self, tenant_id: str, target: str) -> None:
        """Record a target success. Clears failures when CLOSED or increments probes when HALF_OPEN."""
        try:
            current_state = await self.check_state(tenant_id, target)
            primary_state_key = self._state_key(tenant_id, target)
            primary_probes_key = self._probes_key(tenant_id, target)
            primary_failures_key = self._failures_key(tenant_id, target)
            primary_cooldown_key = self._cooldown_key(tenant_id, target)

            mirror_keys: list[tuple[str, str, str, str]] = []
            if self.is_system_target(tenant_id, target) and tenant_id != "system":
                mirror_keys.append((
                    self._state_key(tenant_id, target, force_tenant=True),
                    self._probes_key(tenant_id, target, force_tenant=True),
                    self._failures_key(tenant_id, target, force_tenant=True),
                    self._cooldown_key(tenant_id, target, force_tenant=True),
                ))

            if current_state == CircuitState.HALF_OPEN:
                probes = await self.redis.incr(primary_probes_key)
                for _, p_k, _, _ in mirror_keys:
                    await self.redis.incr(p_k)

                if probes >= self.recovery_threshold:
                    await self.redis.set(primary_state_key, CircuitState.CLOSED.value)
                    await self.redis.delete(
                        primary_failures_key,
                        primary_probes_key,
                        primary_cooldown_key,
                    )
                    for st_k, p_k, f_k, cd_k in mirror_keys:
                        await self.redis.set(st_k, CircuitState.CLOSED.value)
                        await self.redis.delete(f_k, p_k, cd_k)

                    logger.info(
                        "Circuit breaker recovered to CLOSED after successful probes",
                        tenant_id=tenant_id,
                        target=target,
                        probes=probes,
                    )
            elif current_state == CircuitState.CLOSED:
                await self.redis.delete(primary_failures_key, primary_probes_key)
                for _, p_k, f_k, _ in mirror_keys:
                    await self.redis.delete(f_k, p_k)
        except (RedisConnectionError, RedisError, TimeoutError, OSError) as exc:
            logger.warning(
                "Redis unavailable during circuit breaker record_success; ignoring error",
                tenant_id=tenant_id,
                target=target,
                error=str(exc),
            )

    async def acquire_canary_lock(
        self, provider: str, owner_token: str, ttl_seconds: int = 15
    ) -> bool:
        """Acquire an exclusive canary lock for probing a HALF_OPEN provider.

        Command: SET system:circuit_breaker:{provider}:canary_lock {owner_token} NX EX {ttl_seconds}
        Fails closed (returns False) on Redis errors to prevent canary flooding.
        """
        try:
            lock_key = self._canary_lock_key(provider)
            res = await self.redis.set(lock_key, owner_token, ex=ttl_seconds, nx=True)
            return bool(res)
        except (RedisConnectionError, RedisError, TimeoutError, OSError) as exc:
            logger.warning(
                "Redis error acquiring canary lock; failing closed to prevent canary flood",
                provider=provider,
                error=str(exc),
            )
            return False

    async def release_canary_lock(self, provider: str, owner_token: str) -> bool:
        """Release canary lock using Lua script to verify ownership before deletion.

        Script deletes the lock ONLY if the stored value matches owner_token.
        """
        try:
            lock_key = self._canary_lock_key(provider)
            res = await self.redis.eval(LUA_RELEASE_LOCK_SCRIPT, 1, lock_key, owner_token)
            return bool(res == 1 or res == b"1")
        except (RedisConnectionError, RedisError, TimeoutError, OSError) as exc:
            logger.warning(
                "Redis error releasing canary lock",
                provider=provider,
                error=str(exc),
            )
            return False

    async def get_circuit_breaker_state(
        self, tenant_id: str, target: str
    ) -> CircuitBreakerStateDTO:
        """Fetch complete snapshot of target circuit breaker state and counters."""
        try:
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
        except (RedisConnectionError, RedisError, TimeoutError, OSError) as exc:
            logger.warning(
                "Redis error fetching circuit breaker snapshot; returning fallback closed DTO",
                tenant_id=tenant_id,
                target=target,
                error=str(exc),
            )
            return CircuitBreakerStateDTO(
                tenant_id=tenant_id,
                target=target,
                state=CircuitState.CLOSED,
                failures=0,
                last_failure_timestamp=None,
                cooldown_ttl_seconds=0,
            )

    async def force_reset(self, tenant_id: str, target: str) -> bool:
        """Admin operation: immediately force circuit state to CLOSED and clear all error counters."""
        try:
            primary_state_key = self._state_key(tenant_id, target)
            primary_failures_key = self._failures_key(tenant_id, target)
            primary_probes_key = self._probes_key(tenant_id, target)
            primary_cooldown_key = self._cooldown_key(tenant_id, target)
            primary_last_ts_key = self._last_ts_key(tenant_id, target)

            keys_to_delete = [
                primary_failures_key,
                primary_probes_key,
                primary_cooldown_key,
                primary_last_ts_key,
                self._canary_lock_key(target),
            ]
            await self.redis.set(primary_state_key, CircuitState.CLOSED.value)

            if self.is_system_target(tenant_id, target) and tenant_id != "system":
                leg_state_key = self._state_key(tenant_id, target, force_tenant=True)
                await self.redis.set(leg_state_key, CircuitState.CLOSED.value)
                keys_to_delete.extend([
                    self._failures_key(tenant_id, target, force_tenant=True),
                    self._probes_key(tenant_id, target, force_tenant=True),
                    self._cooldown_key(tenant_id, target, force_tenant=True),
                    self._last_ts_key(tenant_id, target, force_tenant=True),
                ])

            await self.redis.delete(*keys_to_delete)
            logger.info(
                "Circuit breaker force reset to CLOSED by administrator",
                tenant_id=tenant_id,
                target=target,
            )
            return True
        except (RedisConnectionError, RedisError, TimeoutError, OSError) as exc:
            logger.warning(
                "Redis error during force_reset",
                tenant_id=tenant_id,
                target=target,
                error=str(exc),
            )
            return False
