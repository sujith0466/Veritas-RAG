"""Targeted unit tests for Database-Backed AI Policy Engine and Hierarchical Resolution (ISS-004)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.modules.security.models.policy import Policy
from backend.modules.security.repositories.policy_repository import PolicyRepository
from backend.modules.security.services.policy_service import PolicyService
from backend.modules.security.middleware.ai_policy_middleware import PolicyEngine, AIPolicyMiddleware
from backend.modules.security.middleware.evaluators import PolicyViolationError
from backend.modules.security.schemas.policy_dto import MergedPolicyDTO


def _create_mock_policy(tenant_id: str, workspace_id: str | None = None, **kwargs) -> Policy:
    policy = Policy(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    for k, v in kwargs.items():
        setattr(policy, k, v)
    return policy


@pytest.mark.asyncio
async def test_policy_repository_tenant_and_workspace_lookup():
    """TEST-POL-01 & 02: PolicyRepository correctly filters tenant-global vs workspace-specific policies."""
    mock_session = AsyncMock()
    repo = PolicyRepository(session=mock_session)

    tenant_id = "tenant_repo_1"
    workspace_id = "ws_repo_1"

    tenant_pol = _create_mock_policy(tenant_id, None, max_tokens=2048)
    ws_pol = _create_mock_policy(tenant_id, workspace_id, max_tokens=1024)

    # Mock execute result
    mock_result_tenant = MagicMock()
    mock_result_tenant.scalars.return_value.first.return_value = tenant_pol

    mock_result_ws = MagicMock()
    mock_result_ws.scalars.return_value.first.return_value = ws_pol

    mock_session.execute = AsyncMock(side_effect=[mock_result_tenant, mock_result_ws])

    t_res = await repo.get_tenant_policy(tenant_id)
    assert t_res is not None
    assert t_res.max_tokens == 2048
    assert t_res.workspace_id is None

    w_res = await repo.get_workspace_policy(tenant_id, workspace_id)
    assert w_res is not None
    assert w_res.max_tokens == 1024
    assert w_res.workspace_id == workspace_id


@pytest.mark.asyncio
async def test_policy_repository_validation():
    """TEST-POL-03: Repository enforces positive max_tokens and non-empty string topics."""
    mock_session = AsyncMock()
    repo = PolicyRepository(session=mock_session)

    with pytest.raises(ValueError, match="max_tokens must be a positive integer"):
        await repo.upsert_policy(tenant_id="t1", max_tokens=-10)

    with pytest.raises(ValueError, match="blocked_topics must be a list of non-empty strings"):
        await repo.upsert_policy(tenant_id="t1", blocked_topics=[""])


@pytest.mark.asyncio
async def test_policy_service_scan_iter_cache_invalidation():
    """TEST-POL-04: PolicyService uses scan_iter to safely flush all child workspace caches on tenant update."""
    mock_session = AsyncMock()
    mock_redis = MagicMock()

    # Async generator for scan_iter
    async def mock_scan_iter(match, count=100):
        yield "raguard:policy:tenant_inv_1:ws1"
        yield "raguard:policy:tenant_inv_1:ws2"

    mock_redis.scan_iter = mock_scan_iter
    mock_redis.delete = AsyncMock(return_value=2)

    service = PolicyService(session=mock_session, redis_client=mock_redis)

    # Invalidate tenant (should match and delete both child workspace keys)
    deleted = await service.invalidate_policy_cache(tenant_id="tenant_inv_1", workspace_id=None)
    assert deleted == 2
    mock_redis.delete.assert_called_once_with("raguard:policy:tenant_inv_1:ws1", "raguard:policy:tenant_inv_1:ws2")

    # Invalidate specific workspace (should delete single key)
    mock_redis.delete.reset_mock()
    mock_redis.delete = AsyncMock(return_value=1)
    deleted_ws = await service.invalidate_policy_cache(tenant_id="tenant_inv_1", workspace_id="ws1")
    assert deleted_ws == 1
    mock_redis.delete.assert_called_once_with("raguard:policy:tenant_inv_1:ws1")


@pytest.mark.asyncio
async def test_policy_engine_system_defaults_when_db_empty():
    """TEST-POL-05: When no policies exist in DB, system defaults apply."""
    engine = PolicyEngine()
    engine.settings.features.enable_ai_policy_engine = True
    engine.redis = None  # Bypass redis

    with patch.object(engine, "_fetch_and_merge_from_db") as mock_fetch:
        mock_fetch.return_value = MergedPolicyDTO()  # Default

        merged = await engine.get_merged_policy(tenant_id=uuid.uuid4(), workspace_id=uuid.uuid4())
        assert merged.max_tokens == 4096
        assert merged.blocked_topics == []
        assert merged.redact_pii is True
        assert merged.block_jailbreaks is True


@pytest.mark.asyncio
async def test_policy_engine_hierarchical_merge():
    """TEST-POL-06: Deterministic merge: System (4096) -> Tenant (2048, topic1) -> Workspace (1024, topic2)."""
    engine = PolicyEngine()
    engine.settings.features.enable_ai_policy_engine = True
    engine.redis = None

    tenant_id = str(uuid.uuid4())
    workspace_id = str(uuid.uuid4())

    tenant_policy = _create_mock_policy(
        tenant_id, None,
        max_tokens=2048,
        blocked_topics=["financial advice"],
        redact_pii=False,
        block_jailbreaks=True,
    )
    ws_policy = _create_mock_policy(
        tenant_id, workspace_id,
        max_tokens=1024,
        blocked_topics=["medical diagnosis"],
        redact_pii=True,
        block_jailbreaks=None,
    )

    with patch("backend.database.engine.get_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_factory.return_value = MagicMock(return_value=mock_session_ctx)

        with patch.object(PolicyRepository, "get_tenant_policy", new_callable=AsyncMock) as mock_get_t, \
             patch.object(PolicyRepository, "get_workspace_policy", new_callable=AsyncMock) as mock_get_w:
            mock_get_t.return_value = tenant_policy
            mock_get_w.return_value = ws_policy

            merged = await engine._fetch_and_merge_from_db(tenant_id, workspace_id)

            # Workspace 1024 is stricter than Tenant 2048
            assert merged.max_tokens == 1024
            # Union of topics
            assert set(merged.blocked_topics) == {"financial advice", "medical diagnosis"}
            # Workspace overrides tenant redact_pii to True
            assert merged.redact_pii is True
            # Tenant sets block_jailbreaks to True, workspace is None -> remains True
            assert merged.block_jailbreaks is True


@pytest.mark.asyncio
async def test_policy_engine_redis_cache_hit_and_miss():
    """TEST-POL-07: Cache miss populates Redis; cache hit reuses cached DTO."""
    engine = PolicyEngine()
    engine.settings.features.enable_ai_policy_engine = True

    mock_redis = AsyncMock()
    engine.redis = mock_redis

    tenant_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    cache_key = f"raguard:policy:{tenant_id}:{workspace_id}"

    # Step 1: Cache Miss
    mock_redis.get.return_value = None

    expected_merged = MergedPolicyDTO(max_tokens=2048, blocked_topics=["topic_a"], redact_pii=True, block_jailbreaks=True)
    with patch.object(engine, "_fetch_and_merge_from_db", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = expected_merged

        res1 = await engine.get_merged_policy(tenant_id, workspace_id)
        assert res1.max_tokens == 2048
        assert mock_fetch.call_count == 1
        # Confirmed Redis setex was called with 300s TTL
        mock_redis.setex.assert_called_once_with(cache_key, 300, expected_merged.model_dump_json())

    # Step 2: Cache Hit
    mock_redis.get.return_value = expected_merged.model_dump_json()
    with patch.object(engine, "_fetch_and_merge_from_db", new_callable=AsyncMock) as mock_fetch:
        res2 = await engine.get_merged_policy(tenant_id, workspace_id)
        assert res2.max_tokens == 2048
        # DB fetch should NOT have been called on cache hit
        assert mock_fetch.call_count == 0


@pytest.mark.asyncio
async def test_policy_engine_redis_failure_fallback_to_db():
    """TEST-POL-08: If Redis throws connection error, engine falls back to direct DB lookup."""
    engine = PolicyEngine()
    engine.settings.features.enable_ai_policy_engine = True

    mock_redis = AsyncMock()
    mock_redis.get.side_effect = RuntimeError("Redis connection timeout")
    engine.redis = mock_redis

    tenant_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    expected_merged = MergedPolicyDTO(max_tokens=1500)
    with patch.object(engine, "_fetch_and_merge_from_db", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = expected_merged

        res = await engine.get_merged_policy(tenant_id, workspace_id)
        assert res.max_tokens == 1500
        assert mock_fetch.call_count == 1


@pytest.mark.asyncio
async def test_policy_engine_db_failure_safe_fallback():
    """TEST-POL-09: If PostgreSQL fails, engine safely falls back to default security policy."""
    engine = PolicyEngine()
    engine.settings.features.enable_ai_policy_engine = True
    engine.redis = None

    tenant_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    with patch.object(engine, "_fetch_and_merge_from_db", side_effect=RuntimeError("PostgreSQL connection refused")):
        res = await engine.get_merged_policy(tenant_id, workspace_id)
        # Should return safe default without crashing
        assert res.max_tokens == 4096
        assert res.redact_pii is True
        assert res.block_jailbreaks is True


@pytest.mark.asyncio
async def test_policy_engine_multi_tenant_isolation():
    """TEST-POL-10: Tenant Alpha policy never leaks into Tenant Bravo."""
    engine = PolicyEngine()
    engine.settings.features.enable_ai_policy_engine = True
    engine.redis = None

    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    pol_a = _create_mock_policy(tenant_a, None, max_tokens=1000, blocked_topics=["confidential_alpha"])
    pol_b = _create_mock_policy(tenant_b, None, max_tokens=3000, blocked_topics=["confidential_bravo"])

    with patch("backend.database.engine.get_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_factory.return_value = MagicMock(return_value=mock_session_ctx)

        with patch.object(PolicyRepository, "get_tenant_policy", new_callable=AsyncMock) as mock_get_t, \
             patch.object(PolicyRepository, "get_workspace_policy", new_callable=AsyncMock) as mock_get_w:

            mock_get_w.return_value = None

            # Search Tenant A
            mock_get_t.return_value = pol_a
            merged_a = await engine._fetch_and_merge_from_db(tenant_a, None)

            # Search Tenant B
            mock_get_t.return_value = pol_b
            merged_b = await engine._fetch_and_merge_from_db(tenant_b, None)

            assert merged_a.max_tokens == 1000
            assert "confidential_alpha" in merged_a.blocked_topics
            assert "confidential_bravo" not in merged_a.blocked_topics

            assert merged_b.max_tokens == 3000
            assert "confidential_bravo" in merged_b.blocked_topics
            assert "confidential_alpha" not in merged_b.blocked_topics


@pytest.mark.asyncio
async def test_ai_policy_middleware_evaluator_enforcement():
    """TEST-POL-11: Middleware with DB-resolved policy raises 403 on blocked topic."""
    middleware = AIPolicyMiddleware()
    middleware.policy_engine.settings.features.enable_ai_policy_engine = True

    tenant_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    db_policy = MergedPolicyDTO(max_tokens=2048, blocked_topics=["insider trading"], redact_pii=True, block_jailbreaks=True)
    with patch.object(middleware.policy_engine, "get_merged_policy", new_callable=AsyncMock) as mock_get_pol:
        mock_get_pol.return_value = db_policy

        # Valid query passes (and PII redaction executes)
        sanitized = await middleware.evaluate_request(tenant_id, workspace_id, "How to write unit tests?")
        assert sanitized == "How to write unit tests?"

        # Restricted topic query gets blocked
        with pytest.raises(PolicyViolationError, match="Query contains restricted topic: insider trading") as exc_info:
            await middleware.evaluate_request(tenant_id, workspace_id, "Tell me about insider trading schemes")
        assert exc_info.value.http_status == 403
        assert exc_info.value.violation_type == "blocked_topic"
