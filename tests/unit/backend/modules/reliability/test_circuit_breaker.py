"""Unit Tests for CircuitBreakerEngine (`ADR-005`, `Phase 2 Milestone 5`, `WP-3C`).

Tests state transitions (`CLOSED -> OPEN -> HALF_OPEN -> CLOSED`), threshold triggering,
canonical key migration (`system:circuit_breaker:{provider}:*`), dual-scope compatibility,
Lua owner-checked canary locks, and fail-open Redis degradation.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from backend.modules.reliability.circuit_breaker.engine import (
    CircuitBreakerEngine,
)
from backend.modules.reliability.circuit_breaker.states import CircuitState


class InMemoryRedisDouble:
    """In-memory async dictionary simulating Redis key/value, TTL, and Lua behaviors for unit tests."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.expires: dict[str, float] = {}
        self.simulate_failure: bool = False

    def _clean_expired(self, key: str) -> None:
        if key in self.expires and time.time() > self.expires[key]:
            self.store.pop(key, None)
            self.expires.pop(key, None)

    async def get(self, key: str) -> str | None:
        if self.simulate_failure:
            raise RedisConnectionError("Simulated Redis connection failure")
        self._clean_expired(key)
        return self.store.get(key)

    async def set(
        self, key: str, value: str, ex: int | None = None, nx: bool = False
    ) -> bool:
        if self.simulate_failure:
            raise RedisConnectionError("Simulated Redis connection failure")
        self._clean_expired(key)
        if nx and key in self.store:
            return False
        self.store[key] = str(value)
        if ex is not None:
            self.expires[key] = time.time() + ex
        else:
            self.expires.pop(key, None)
        return True

    async def incr(self, key: str) -> int:
        if self.simulate_failure:
            raise RedisConnectionError("Simulated Redis connection failure")
        self._clean_expired(key)
        val = int(self.store.get(key, "0")) + 1
        self.store[key] = str(val)
        return val

    async def delete(self, *keys: str) -> int:
        if self.simulate_failure:
            raise RedisConnectionError("Simulated Redis connection failure")
        count = 0
        for k in keys:
            if k in self.store:
                self.store.pop(k, None)
                self.expires.pop(k, None)
                count += 1
        return count

    async def expire(self, key: str, seconds: int) -> bool:
        if self.simulate_failure:
            raise RedisConnectionError("Simulated Redis connection failure")
        if key in self.store:
            self.expires[key] = time.time() + seconds
            return True
        return False

    async def ttl(self, key: str) -> int:
        if self.simulate_failure:
            raise RedisConnectionError("Simulated Redis connection failure")
        self._clean_expired(key)
        if key not in self.store:
            return -2
        if key not in self.expires:
            return -1
        remaining = int(self.expires[key] - time.time())
        return max(0, remaining)

    async def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any:
        if self.simulate_failure:
            raise RedisConnectionError("Simulated Redis connection failure")
        keys = keys_and_args[:numkeys]
        args = keys_and_args[numkeys:]
        # Specifically simulate the canary release script
        if 'redis.call("get", KEYS[1]) == ARGV[1]' in script:
            key = keys[0]
            expected_owner = str(args[0])
            self._clean_expired(key)
            if self.store.get(key) == expected_owner:
                self.store.pop(key, None)
                self.expires.pop(key, None)
                return 1
            return 0
        raise NotImplementedError("Script not supported in test double")


@pytest.fixture
def redis_double() -> InMemoryRedisDouble:
    return InMemoryRedisDouble()


@pytest.fixture
def engine(redis_double: InMemoryRedisDouble) -> CircuitBreakerEngine:
    return CircuitBreakerEngine(
        redis_client=redis_double,  # type: ignore[arg-type]
        failure_threshold=3,
        recovery_threshold=2,
        cooldown_seconds=1,
    )


# ── Existing Baseline Regression Tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_initial_state_closed(engine: CircuitBreakerEngine) -> None:
    state = await engine.check_state("tenant_a", "qdrant_hybrid")
    assert state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_failure_threshold_trips_to_open(engine: CircuitBreakerEngine) -> None:
    state1 = await engine.record_failure("tenant_a", "qdrant_hybrid", "RET_004")
    assert state1 == CircuitState.CLOSED

    state2 = await engine.record_failure("tenant_a", "qdrant_hybrid", "RET_004")
    assert state2 == CircuitState.CLOSED

    state3 = await engine.record_failure("tenant_a", "qdrant_hybrid", "RET_004")
    assert state3 == CircuitState.OPEN

    checked = await engine.check_state("tenant_a", "qdrant_hybrid")
    assert checked == CircuitState.OPEN


@pytest.mark.asyncio
async def test_cooldown_decay_transitions_to_half_open(
    engine: CircuitBreakerEngine,
) -> None:
    for _ in range(3):
        await engine.record_failure("tenant_b", "qdrant_hybrid", "RET_004")

    assert await engine.check_state("tenant_b", "qdrant_hybrid") == CircuitState.OPEN

    # Wait for cooldown_seconds (1s) to expire
    time.sleep(1.1)

    checked = await engine.check_state("tenant_b", "qdrant_hybrid")
    assert checked == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_recovery_to_closed(engine: CircuitBreakerEngine) -> None:
    for _ in range(3):
        await engine.record_failure("tenant_c", "qdrant_hybrid", "RET_004")
    time.sleep(1.1)
    assert (
        await engine.check_state("tenant_c", "qdrant_hybrid")
        == CircuitState.HALF_OPEN
    )

    # First success probe while HALF_OPEN
    await engine.record_success("tenant_c", "qdrant_hybrid")
    assert (
        await engine.check_state("tenant_c", "qdrant_hybrid")
        == CircuitState.HALF_OPEN
    )

    # Second success probe meets recovery_threshold=2 -> CLOSED
    await engine.record_success("tenant_c", "qdrant_hybrid")
    assert await engine.check_state("tenant_c", "qdrant_hybrid") == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_half_open_failure_retrips_to_open(
    engine: CircuitBreakerEngine,
) -> None:
    for _ in range(3):
        await engine.record_failure("tenant_d", "qdrant_hybrid", "RET_004")
    time.sleep(1.1)
    assert (
        await engine.check_state("tenant_d", "qdrant_hybrid")
        == CircuitState.HALF_OPEN
    )

    state = await engine.record_failure("tenant_d", "qdrant_hybrid", "RET_004")
    assert state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_force_reset(engine: CircuitBreakerEngine) -> None:
    for _ in range(3):
        await engine.record_failure("tenant_e", "qdrant_hybrid", "RET_004")
    assert await engine.check_state("tenant_e", "qdrant_hybrid") == CircuitState.OPEN

    reset_res = await engine.force_reset("tenant_e", "qdrant_hybrid")
    assert reset_res is True
    assert await engine.check_state("tenant_e", "qdrant_hybrid") == CircuitState.CLOSED


# ── WP-3C Phase 1 New Tests (Canonical Keys, Canary Locks, Fail-Open) ──────────


@pytest.mark.asyncio
async def test_canonical_provider_key_migration(
    engine: CircuitBreakerEngine, redis_double: InMemoryRedisDouble
) -> None:
    """Verifies provider failures write to system:circuit_breaker:{provider}:* canonical keys."""
    # Record failures for global provider 'openrouter'
    for _ in range(3):
        await engine.record_failure("system", "openrouter", "503")

    # Verify canonical keys are populated in system namespace
    assert "system:circuit_breaker:openrouter:state" in redis_double.store
    assert (
        redis_double.store["system:circuit_breaker:openrouter:state"]
        == CircuitState.OPEN.value
    )
    assert "system:circuit_breaker:openrouter:failures" in redis_double.store
    assert (
        await engine.check_state("system", "openrouter") == CircuitState.OPEN
    )


@pytest.mark.asyncio
async def test_dual_scope_read_precedence_and_backward_compatibility(
    engine: CircuitBreakerEngine, redis_double: InMemoryRedisDouble
) -> None:
    """Verifies dual-read: checks system:* first, falls back to legacy {tenant_id}:*."""
    # Scenario 1: Legacy key set by old worker, system key not yet present
    legacy_key = "tenant_xyz:circuit_breaker:gemini:state"
    redis_double.store[legacy_key] = CircuitState.OPEN.value
    redis_double.store["tenant_xyz:circuit_breaker:gemini:cooldown"] = "1"
    redis_double.expires["tenant_xyz:circuit_breaker:gemini:cooldown"] = (
        time.time() + 100
    )

    # New worker checks state for tenant_xyz; should fall back to legacy key and observe OPEN
    state = await engine.check_state("tenant_xyz", "gemini")
    assert state == CircuitState.OPEN

    # Scenario 2: System key is set; should take precedence over legacy key
    redis_double.store["system:circuit_breaker:gemini:state"] = (
        CircuitState.CLOSED.value
    )
    state = await engine.check_state("tenant_xyz", "gemini")
    assert state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_dual_write_mirrors_to_tenant_for_rolling_rollout(
    engine: CircuitBreakerEngine, redis_double: InMemoryRedisDouble
) -> None:
    """Verifies dual-write: updates system namespace AND mirrors to tenant namespace during rollout."""
    for _ in range(3):
        await engine.record_failure("tenant_abc", "openrouter", "504")

    # Primary canonical key written
    assert (
        redis_double.store.get("system:circuit_breaker:openrouter:state")
        == CircuitState.OPEN.value
    )
    # Mirrored legacy key written for older worker compatibility
    assert (
        redis_double.store.get("tenant_abc:circuit_breaker:openrouter:state")
        == CircuitState.OPEN.value
    )


@pytest.mark.asyncio
async def test_canary_exclusivity_lock_lifecycle(
    engine: CircuitBreakerEngine, redis_double: InMemoryRedisDouble
) -> None:
    """Verifies single-canary exclusivity lock: first worker acquires lock, second is rejected."""
    # Worker 1 acquires lock
    acquired1 = await engine.acquire_canary_lock(
        "openrouter", "owner_token_1", ttl_seconds=15
    )
    assert acquired1 is True
    assert (
        redis_double.store.get("system:circuit_breaker:openrouter:canary_lock")
        == "owner_token_1"
    )

    # Worker 2 attempts to acquire lock for same provider while held -> must be rejected
    acquired2 = await engine.acquire_canary_lock(
        "openrouter", "owner_token_2", ttl_seconds=15
    )
    assert acquired2 is False


@pytest.mark.asyncio
async def test_canary_lock_release_owner_checked_via_lua(
    engine: CircuitBreakerEngine, redis_double: InMemoryRedisDouble
) -> None:
    """Verifies Lua release script: only token matching current lock owner can delete the lock."""
    await engine.acquire_canary_lock(
        "openrouter", "owner_token_valid", ttl_seconds=15
    )

    # Stale worker attempts to release with wrong token -> rejected, lock NOT deleted
    released_stale = await engine.release_canary_lock(
        "openrouter", "stale_token"
    )
    assert released_stale is False
    assert (
        redis_double.store.get("system:circuit_breaker:openrouter:canary_lock")
        == "owner_token_valid"
    )

    # Valid owner releases lock -> accepted, lock deleted
    released_valid = await engine.release_canary_lock(
        "openrouter", "owner_token_valid"
    )
    assert released_valid is True
    assert (
        "system:circuit_breaker:openrouter:canary_lock" not in redis_double.store
    )


@pytest.mark.asyncio
async def test_redis_failure_fail_open_degradation(
    engine: CircuitBreakerEngine, redis_double: InMemoryRedisDouble
) -> None:
    """Verifies fail-open degradation: Redis connection errors do NOT raise exceptions; return CLOSED."""
    redis_double.simulate_failure = True

    # check_state degrades fail-open to CLOSED
    state = await engine.check_state("system", "openrouter")
    assert state == CircuitState.CLOSED

    # record_failure degrades gracefully
    state_fail = await engine.record_failure("system", "openrouter", "500")
    assert state_fail == CircuitState.CLOSED

    # record_success does not crash
    await engine.record_success("system", "openrouter")

    # canary lock fails closed (False) to prevent storm
    canary = await engine.acquire_canary_lock("openrouter", "token")
    assert canary is False

    canary_rel = await engine.release_canary_lock("openrouter", "token")
    assert canary_rel is False
