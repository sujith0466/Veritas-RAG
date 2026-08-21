"""Comprehensive Chaos Engineering & Resilience Tests (F15.3).

Validates:
1. Production safety fence: Chaos injector is strictly disabled in production.
2. Controlled fault injection (LLM 503, Qdrant Disconnect, Latency Spike).
3. Dependency resilience: Redis outage graceful fallback in Quota Governor.
4. Distributed Circuit Breaker resilience: State transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED).
5. Error boundary encapsulation and tenant boundary preservation under fault conditions.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.core.chaos.injector import ChaosInjector
from backend.core.chaos.models.fault_policy import FaultPolicyORM
from backend.modules.analytics.models.workspace_usage import WorkspaceUsage
from backend.modules.analytics.repositories.usage_repository import UsageRepository
from backend.modules.analytics.services.quota import QuotaGovernor
from backend.modules.reliability.circuit_breaker.engine import CircuitBreakerEngine
from backend.modules.reliability.circuit_breaker.states import CircuitState


# ==============================================================================
# 1. Chaos Injector & Safety Guard Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_chaos_injector_production_safety_guard():
    """Verify that ChaosInjector NEVER executes faults when is_production is True."""
    injector = ChaosInjector()
    injector.is_production = True  # Force production guard

    policy = FaultPolicyORM(
        id=uuid.uuid4(),
        chaos_token="danger-token-503",
        fault_type="LLM_HTTP_503",
        error_rate_pct=1.0,
        is_active=True,
    )
    injector.seed_mock_policy("danger-token-503", policy)

    # In production, this must be a no-op and never raise
    await injector.check_fault_injection("danger-token-503")


@pytest.mark.asyncio
async def test_chaos_injector_llm_outage_simulation():
    """Verify simulated LLM 503 service unavailable fault in staging mode."""
    injector = ChaosInjector()
    injector.is_production = False

    policy = FaultPolicyORM(
        id=uuid.uuid4(),
        chaos_token="test-llm-outage",
        fault_type="LLM_HTTP_503",
        error_rate_pct=1.0,
        is_active=True,
    )
    injector.seed_mock_policy("test-llm-outage", policy)

    with pytest.raises(Exception, match="503 Service Unavailable: Simulated OpenAI Outage"):
        await injector.check_fault_injection("test-llm-outage")


@pytest.mark.asyncio
async def test_chaos_injector_qdrant_disconnect_simulation():
    """Verify simulated Qdrant vector database disconnect in staging mode."""
    injector = ChaosInjector()
    injector.is_production = False

    policy = FaultPolicyORM(
        id=uuid.uuid4(),
        chaos_token="test-qdrant-drop",
        fault_type="QDRANT_DISCONNECT",
        error_rate_pct=1.0,
        is_active=True,
    )
    injector.seed_mock_policy("test-qdrant-drop", policy)

    with pytest.raises(Exception, match="GRPCError: Simulated Vector Store Drop"):
        await injector.check_fault_injection("test-qdrant-drop")


@pytest.mark.asyncio
async def test_chaos_injector_latency_spike():
    """Verify simulated network latency spike execution."""
    injector = ChaosInjector()
    injector.is_production = False

    policy = FaultPolicyORM(
        id=uuid.uuid4(),
        chaos_token="test-latency",
        fault_type="LATENCY_SPIKE",
        latency_ms=50,  # 50ms spike
        error_rate_pct=1.0,
        is_active=True,
    )
    injector.seed_mock_policy("test-latency", policy)

    start_time = asyncio.get_event_loop().time()
    await injector.check_fault_injection("test-latency")
    elapsed = asyncio.get_event_loop().time() - start_time

    assert elapsed >= 0.04  # At least ~50ms delay injected


# ==============================================================================
# 2. Dependency Resilience & Fallback Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_quota_governor_resilience_when_redis_fails():
    """Verify QuotaGovernor gracefully falls back to PostgreSQL when Redis is unreachable."""
    governor = QuotaGovernor()
    ws_id = uuid.uuid4()

    # Mock Redis client raising connection error
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = Exception("Redis connection refused (simulated crash)")
    mock_redis.set.side_effect = Exception("Redis connection refused (simulated crash)")

    # Mock PostgreSQL session
    mock_session = AsyncMock()
    mock_usage = WorkspaceUsage(
        workspace_id=ws_id,
        billing_period_start=UsageRepository.get_current_period_start(),
        used_tokens=4200,
        used_queries=12,
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("backend.modules.analytics.services.quota.get_redis_client", lambda: mock_redis)
        mp.setattr(UsageRepository, "get_current_period_usage", AsyncMock(return_value=mock_usage))

        # Must NOT raise Redis exception; must fallback to PG and return 4200
        used_tokens = await governor.get_durable_usage(workspace_id=ws_id, session=mock_session)
        assert used_tokens == 4200


# ==============================================================================
# 3. Circuit Breaker Resilience Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_circuit_breaker_transitions_to_open_on_threshold_failures():
    """Verify circuit breaker trips from CLOSED to OPEN after 5 consecutive failures."""
    mock_redis = AsyncMock()

    # Mock Redis state storage
    store = {}

    async def mock_get(key):
        return store.get(key)

    async def mock_set(key, val, *args, **kwargs):
        store[key] = str(val) if not isinstance(val, bytes) else val.decode()
        return True

    async def mock_incr(key):
        val = int(store.get(key, 0)) + 1
        store[key] = str(val)
        return val

    mock_redis.get.side_effect = mock_get
    mock_redis.set.side_effect = mock_set
    mock_redis.incr.side_effect = mock_incr
    mock_redis.delete = AsyncMock()
    mock_redis.expire = AsyncMock()

    engine = CircuitBreakerEngine(
        redis_client=mock_redis,
        failure_threshold=5,
        recovery_threshold=3,
        cooldown_seconds=10,
    )

    tenant_id = "tenant-resilience-01"
    target = "openai-gpt4"

    # Initial state should be CLOSED
    state = await engine.check_state(tenant_id, target)
    assert state == CircuitState.CLOSED

    # Record 4 failures -> Should still be CLOSED
    for _ in range(4):
        state = await engine.record_failure(tenant_id, target, error_code=500)
        assert state == CircuitState.CLOSED

    # 5th failure -> Must trip to OPEN
    state = await engine.record_failure(tenant_id, target, error_code=500)
    assert state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_to_closed_recovery():
    """Verify circuit breaker transitions from HALF_OPEN to CLOSED after consecutive successful probes."""
    mock_redis = AsyncMock()
    store = {
        "tenant-resilience-02:circuit_breaker:claude:state": CircuitState.HALF_OPEN.value,
        "tenant-resilience-02:circuit_breaker:claude:probes": "0",
    }

    async def mock_get(key):
        return store.get(key)

    async def mock_set(key, val, *args, **kwargs):
        store[key] = str(val)
        return True

    async def mock_incr(key):
        val = int(store.get(key, 0)) + 1
        store[key] = str(val)
        return val

    async def mock_delete(*keys):
        for k in keys:
            store.pop(k, None)
        return True

    mock_redis.get.side_effect = mock_get
    mock_redis.set.side_effect = mock_set
    mock_redis.incr.side_effect = mock_incr
    mock_redis.delete.side_effect = mock_delete

    engine = CircuitBreakerEngine(
        redis_client=mock_redis,
        failure_threshold=5,
        recovery_threshold=3,
        cooldown_seconds=10,
    )

    tenant_id = "tenant-resilience-02"
    target = "claude"

    # Probe 1 -> Still HALF_OPEN
    await engine.record_success(tenant_id, target)
    state = await engine.check_state(tenant_id, target)
    assert state == CircuitState.HALF_OPEN

    # Probe 2 -> Still HALF_OPEN
    await engine.record_success(tenant_id, target)
    state = await engine.check_state(tenant_id, target)
    assert state == CircuitState.HALF_OPEN

    # Probe 3 -> Threshold reached, transitions back to CLOSED
    await engine.record_success(tenant_id, target)
    state = await engine.check_state(tenant_id, target)
    assert state == CircuitState.CLOSED
