"""Feature Flag Evaluation Engine.

Executes sub-millisecond, multi-tiered (L1 In-Memory -> L2 Redis -> L3 Postgres) feature flag evaluations
following the deterministic 7-step priority resolution pipeline.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import time
from typing import Any
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.feature_flag import FeatureFlag, FlagLifecycleState
from backend.models.entities.feature_flag_workspace_rule import FeatureFlagWorkspaceRule
from backend.observability.metrics.prometheus import (
    record_feature_flag_cache_hit,
    record_feature_flag_cache_miss,
    record_feature_flag_duration,
    record_feature_flag_evaluation,
)
from backend.repositories.feature_flag import (
    FeatureFlagRepository,
    FeatureFlagWorkspaceRuleRepository,
)

logger = structlog.get_logger(__name__)

# L1 In-Memory cache dictionary: {cache_key: (timestamp, data)}
_L1_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_L1_TTL_SECONDS = 15.0
_L2_TTL_SECONDS = 300


def _murmur3_32_seedless(key_bytes: bytes, seed: int = 0) -> int:
    """Pure-Python implementation of MurmurHash3 32-bit for deterministic percentage rollouts."""
    def _fmix(h: int) -> int:
        h ^= h >> 16
        h = (h * 0x85EBCA6B) & 0xFFFFFFFF
        h ^= h >> 13
        h = (h * 0xC2B2AE35) & 0xFFFFFFFF
        h ^= h >> 16
        return h

    length = len(key_bytes)
    nblocks = length // 4
    h1 = seed & 0xFFFFFFFF

    c1 = 0xCC9E2D51
    c2 = 0x1B873593

    # Body
    for i in range(0, nblocks * 4, 4):
        k1 = (
            key_bytes[i]
            | (key_bytes[i + 1] << 8)
            | (key_bytes[i + 2] << 16)
            | (key_bytes[i + 3] << 24)
        )
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF

        h1 ^= k1
        h1 = ((h1 << 13) | (h1 >> 19)) & 0xFFFFFFFF
        h1 = (h1 * 5 + 0xE6546B64) & 0xFFFFFFFF

    # Tail
    tail_index = nblocks * 4
    k1 = 0
    tail_len = length & 3

    if tail_len >= 3:
        k1 ^= key_bytes[tail_index + 2] << 16
    if tail_len >= 2:
        k1 ^= key_bytes[tail_index + 1] << 8
    if tail_len >= 1:
        k1 ^= key_bytes[tail_index]
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF
        h1 ^= k1

    # Finalization
    h1 ^= length
    return _fmix(h1)


def is_entity_in_rollout(flag_key: str, entity_id: str, rollout_percentage: int) -> bool:
    """Evaluate whether an entity falls within a deterministic percentage bucket [0, 100)."""
    if rollout_percentage >= 100:
        return True
    if rollout_percentage <= 0:
        return False
    combined_key = f"{flag_key}:{entity_id}".encode("utf-8")
    hash_val = _murmur3_32_seedless(combined_key, seed=0)
    bucket = (hash_val & 0x7FFFFFFF) % 100
    return bucket < rollout_percentage


def validate_no_circular_dependencies(
    flag_key: str,
    prerequisites: list[str],
    full_dependency_graph: dict[str, list[str]],
) -> None:
    """Validate dependency DAG using Depth-First Search cycle detection."""
    visited: set[str] = set()
    rec_stack: set[str] = set()

    graph = {**full_dependency_graph, flag_key: prerequisites}

    def _dfs(node: str) -> None:
        visited.add(node)
        rec_stack.add(node)

        for neighbor in graph.get(node, []):
            if neighbor in rec_stack:
                raise ValueError(
                    f"Circular prerequisite dependency detected: {node} -> {neighbor}"
                )
            if neighbor not in visited:
                _dfs(neighbor)

        rec_stack.remove(node)

    _dfs(flag_key)


@dataclass
class EvaluationContext:
    """Runtime context for feature flag evaluation."""
    workspace_id: uuid.UUID
    user_id: uuid.UUID | None = None
    user_email: str | None = None
    workspace_role: str | None = None
    environment: str = "production"
    custom_attributes: dict[str, Any] | None = None


@dataclass
class EvaluationResult:
    """Result of feature flag evaluation."""
    flag_key: str
    is_enabled: bool
    variant: dict[str, Any]
    reason: str
    tier_served: str
    evaluated_at: datetime


class FeatureFlagEvaluationService:
    """Ultra-low latency evaluation service for feature flags."""

    def __init__(
        self,
        flag_repo: FeatureFlagRepository,
        rule_repo: FeatureFlagWorkspaceRuleRepository,
    ) -> None:
        self.flag_repo = flag_repo
        self.rule_repo = rule_repo

    async def _get_compiled_flag_and_rule(
        self,
        session: AsyncSession,
        flag_key: str,
        workspace_id: uuid.UUID,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
        """Multi-tier cache retrieval for flag definition and workspace rule."""
        cache_key = f"ff:ws:{workspace_id}:{flag_key}"
        now_ts = time.time()

        # 1. Check L1 Memory Cache
        if cache_key in _L1_CACHE:
            ts, data = _L1_CACHE[cache_key]
            if now_ts - ts < _L1_TTL_SECONDS:
                record_feature_flag_cache_hit(tier="L1_memory")
                return data.get("flag"), data.get("rule"), "L1_memory"
            else:
                _L1_CACHE.pop(cache_key, None)

        record_feature_flag_cache_miss(tier="L1_memory")

        # 2. Check L2 Redis Cache
        try:
            from backend.cache.client import get_redis_client
            redis = get_redis_client()
            if redis:
                cached_bytes = await redis.get(cache_key)
                if cached_bytes:
                    data = json.loads(cached_bytes)
                    _L1_CACHE[cache_key] = (now_ts, data)
                    record_feature_flag_cache_hit(tier="L2_redis")
                    return data.get("flag"), data.get("rule"), "L2_redis"
        except Exception as e:
            logger.warning("Redis L2 cache read error", error=str(e))

        record_feature_flag_cache_miss(tier="L2_redis")

        # 3. L3 PostgreSQL Fallback
        flag = await self.flag_repo.get_by_key(flag_key)
        if not flag:
            return None, None, "L3_postgres"

        rule = await self.rule_repo.get_by_flag_and_workspace(flag.id, workspace_id)

        flag_dict = {
            "id": str(flag.id),
            "key": flag.key,
            "lifecycle_state": flag.lifecycle_state,
            "default_enabled": flag.default_enabled,
            "is_killswitch_active": flag.is_killswitch_active,
            "prerequisite_flag_keys": flag.prerequisite_flag_keys,
            "default_variant_json": flag.default_variant_json,
            "target_environments": flag.target_environments.split(","),
        }
        rule_dict = (
            {
                "id": str(rule.id),
                "is_enabled": rule.is_enabled,
                "rollout_percentage": rule.rollout_percentage,
                "activation_start_at": rule.activation_start_at.isoformat()
                if rule.activation_start_at
                else None,
                "activation_end_at": rule.activation_end_at.isoformat()
                if rule.activation_end_at
                else None,
                "targeting_conditions_json": rule.targeting_conditions_json,
                "custom_variant_json": rule.custom_variant_json,
            }
            if rule
            else None
        )

        cache_payload = {"flag": flag_dict, "rule": rule_dict}
        _L1_CACHE[cache_key] = (now_ts, cache_payload)

        try:
            from backend.cache.client import get_redis_client
            redis = get_redis_client()
            if redis:
                await redis.set(cache_key, json.dumps(cache_payload), ex=_L2_TTL_SECONDS)
        except Exception as e:
            logger.warning("Redis L2 cache write error", error=str(e))

        return flag_dict, rule_dict, "L3_postgres"

    async def evaluate_flag(
        self,
        session: AsyncSession,
        flag_key: str,
        context: EvaluationContext,
        _depth: int = 0,
    ) -> EvaluationResult:
        """Deterministic 7-Step Evaluation Priority Resolution Pipeline."""
        start_time = time.perf_counter()
        now_dt = datetime.now(timezone.utc)

        if _depth > 10:
            return EvaluationResult(
                flag_key=flag_key,
                is_enabled=False,
                variant={},
                reason="MAX_RECURSION_DEPTH_EXCEEDED",
                tier_served="L1_memory",
                evaluated_at=now_dt,
            )

        flag_data, rule_data, tier = await self._get_compiled_flag_and_rule(
            session=session,
            flag_key=flag_key,
            workspace_id=context.workspace_id,
        )

        if not flag_data:
            duration = time.perf_counter() - start_time
            record_feature_flag_duration(tier=tier, duration_seconds=duration)
            record_feature_flag_evaluation(flag_key=flag_key, result="false", reason="FLAG_NOT_FOUND")
            return EvaluationResult(
                flag_key=flag_key,
                is_enabled=False,
                variant={},
                reason="FLAG_NOT_FOUND",
                tier_served=tier,
                evaluated_at=now_dt,
            )

        # Check Lifecycle State
        state = flag_data.get("lifecycle_state", FlagLifecycleState.DRAFT.value)
        if state == FlagLifecycleState.ARCHIVED.value or state == FlagLifecycleState.DELETED.value:
            return EvaluationResult(
                flag_key=flag_key,
                is_enabled=False,
                variant=flag_data.get("default_variant_json", {}),
                reason="FLAG_ARCHIVED",
                tier_served=tier,
                evaluated_at=now_dt,
            )

        # Step 1: Global / Flag Kill Switch
        if flag_data.get("is_killswitch_active", False):
            duration = time.perf_counter() - start_time
            record_feature_flag_duration(tier=tier, duration_seconds=duration)
            record_feature_flag_evaluation(flag_key=flag_key, result="false", reason="KILLSWITCH")
            return EvaluationResult(
                flag_key=flag_key,
                is_enabled=False,
                variant=flag_data.get("default_variant_json", {}),
                reason="KILLSWITCH",
                tier_served=tier,
                evaluated_at=now_dt,
            )

        # Step 2: Prerequisite Dependency Graph Check
        prerequisites = flag_data.get("prerequisite_flag_keys", [])
        for prereq_key in prerequisites:
            prereq_eval = await self.evaluate_flag(
                session=session,
                flag_key=prereq_key,
                context=context,
                _depth=_depth + 1,
            )
            if not prereq_eval.is_enabled:
                duration = time.perf_counter() - start_time
                record_feature_flag_duration(tier=tier, duration_seconds=duration)
                record_feature_flag_evaluation(
                    flag_key=flag_key, result="false", reason="PREREQUISITE_FAILED"
                )
                return EvaluationResult(
                    flag_key=flag_key,
                    is_enabled=False,
                    variant=flag_data.get("default_variant_json", {}),
                    reason=f"PREREQUISITE_FAILED:{prereq_key}",
                    tier_served=tier,
                    evaluated_at=now_dt,
                )

        # Step 3: Workspace Override Check
        if not rule_data:
            # Fallback to Global Default
            default_enabled = flag_data.get("default_enabled", False)
            duration = time.perf_counter() - start_time
            record_feature_flag_duration(tier=tier, duration_seconds=duration)
            record_feature_flag_evaluation(
                flag_key=flag_key,
                result="true" if default_enabled else "false",
                reason="GLOBAL_DEFAULT",
            )
            return EvaluationResult(
                flag_key=flag_key,
                is_enabled=default_enabled,
                variant=flag_data.get("default_variant_json", {}),
                reason="GLOBAL_DEFAULT",
                tier_served=tier,
                evaluated_at=now_dt,
            )

        if not rule_data.get("is_enabled", True):
            duration = time.perf_counter() - start_time
            record_feature_flag_duration(tier=tier, duration_seconds=duration)
            record_feature_flag_evaluation(
                flag_key=flag_key, result="false", reason="WORKSPACE_OVERRIDE_DISABLED"
            )
            return EvaluationResult(
                flag_key=flag_key,
                is_enabled=False,
                variant=rule_data.get("custom_variant_json") or flag_data.get("default_variant_json", {}),
                reason="WORKSPACE_OVERRIDE_DISABLED",
                tier_served=tier,
                evaluated_at=now_dt,
            )

        # Step 4: User / Attribute Targeting Conditions Match
        targeting = rule_data.get("targeting_conditions_json", [])
        if targeting:
            matched_user = False
            for cond in targeting:
                cond_type = cond.get("type")
                target_vals = cond.get("values", [])
                if cond_type == "USER_ID" and context.user_id and str(context.user_id) in target_vals:
                    matched_user = True
                    break
                elif cond_type == "EMAIL_DOMAIN" and context.user_email:
                    domain = context.user_email.split("@")[-1].lower()
                    if domain in [v.lower() for v in target_vals]:
                        matched_user = True
                        break

            if matched_user:
                duration = time.perf_counter() - start_time
                record_feature_flag_duration(tier=tier, duration_seconds=duration)
                record_feature_flag_evaluation(
                    flag_key=flag_key, result="true", reason="USER_TARGETING_MATCH"
                )
                return EvaluationResult(
                    flag_key=flag_key,
                    is_enabled=True,
                    variant=rule_data.get("custom_variant_json") or flag_data.get("default_variant_json", {}),
                    reason="USER_TARGETING_MATCH",
                    tier_served=tier,
                    evaluated_at=now_dt,
                )

        # Step 5: Role Targeting Match
        for cond in targeting:
            if cond.get("type") == "ROLE" and context.workspace_role:
                target_roles = [r.upper() for r in cond.get("values", [])]
                if context.workspace_role.upper() in target_roles:
                    duration = time.perf_counter() - start_time
                    record_feature_flag_duration(tier=tier, duration_seconds=duration)
                    record_feature_flag_evaluation(
                        flag_key=flag_key, result="true", reason="ROLE_TARGETING_MATCH"
                    )
                    return EvaluationResult(
                        flag_key=flag_key,
                        is_enabled=True,
                        variant=rule_data.get("custom_variant_json") or flag_data.get("default_variant_json", {}),
                        reason="ROLE_TARGETING_MATCH",
                        tier_served=tier,
                        evaluated_at=now_dt,
                    )

        # Step 6: Percentage Rollout Check (MurmurHash3)
        rollout_pct = rule_data.get("rollout_percentage", 100)
        entity_id_for_rollout = str(context.user_id) if context.user_id else str(context.workspace_id)
        if not is_entity_in_rollout(flag_key, entity_id_for_rollout, rollout_pct):
            duration = time.perf_counter() - start_time
            record_feature_flag_duration(tier=tier, duration_seconds=duration)
            record_feature_flag_evaluation(
                flag_key=flag_key, result="false", reason="PERCENTAGE_EXCLUDED"
            )
            return EvaluationResult(
                flag_key=flag_key,
                is_enabled=False,
                variant=flag_data.get("default_variant_json", {}),
                reason="PERCENTAGE_EXCLUDED",
                tier_served=tier,
                evaluated_at=now_dt,
            )

        # Step 7: Date Activation Window Check
        start_at_str = rule_data.get("activation_start_at")
        end_at_str = rule_data.get("activation_end_at")

        if start_at_str:
            start_dt = datetime.fromisoformat(start_at_str)
            if now_dt < start_dt:
                duration = time.perf_counter() - start_time
                record_feature_flag_duration(tier=tier, duration_seconds=duration)
                record_feature_flag_evaluation(
                    flag_key=flag_key, result="false", reason="BEFORE_DATE_WINDOW"
                )
                return EvaluationResult(
                    flag_key=flag_key,
                    is_enabled=False,
                    variant=flag_data.get("default_variant_json", {}),
                    reason="BEFORE_DATE_WINDOW",
                    tier_served=tier,
                    evaluated_at=now_dt,
                )

        if end_at_str:
            end_dt = datetime.fromisoformat(end_at_str)
            if now_dt > end_dt:
                duration = time.perf_counter() - start_time
                record_feature_flag_duration(tier=tier, duration_seconds=duration)
                record_feature_flag_evaluation(
                    flag_key=flag_key, result="false", reason="AFTER_DATE_WINDOW"
                )
                return EvaluationResult(
                    flag_key=flag_key,
                    is_enabled=False,
                    variant=flag_data.get("default_variant_json", {}),
                    reason="AFTER_DATE_WINDOW",
                    tier_served=tier,
                    evaluated_at=now_dt,
                )

        # Successfully Enabled via Workspace Rule
        duration = time.perf_counter() - start_time
        record_feature_flag_duration(tier=tier, duration_seconds=duration)
        record_feature_flag_evaluation(
            flag_key=flag_key, result="true", reason="WORKSPACE_RULE_ENABLED"
        )
        return EvaluationResult(
            flag_key=flag_key,
            is_enabled=True,
            variant=rule_data.get("custom_variant_json") or flag_data.get("default_variant_json", {}),
            reason="WORKSPACE_RULE_ENABLED",
            tier_served=tier,
            evaluated_at=now_dt,
        )

    async def evaluate_all_flags_for_workspace(
        self,
        session: AsyncSession,
        context: EvaluationContext,
    ) -> dict[str, EvaluationResult]:
        """Evaluate all active feature flags for a given workspace and user context."""
        flags = await self.flag_repo.list_active_flags()
        results: dict[str, EvaluationResult] = {}
        for flag in flags:
            results[flag.key] = await self.evaluate_flag(
                session=session,
                flag_key=flag.key,
                context=context,
            )
        return results

    @staticmethod
    def invalidate_local_cache(workspace_id: uuid.UUID | None = None, flag_key: str | None = None) -> None:
        """Clear L1 memory cache keys matching pattern."""
        keys_to_delete = []
        for k in _L1_CACHE.keys():
            if workspace_id and f"ff:ws:{workspace_id}:" in k:
                keys_to_delete.append(k)
            elif flag_key and f":{flag_key}" in k:
                keys_to_delete.append(k)
            elif not workspace_id and not flag_key:
                keys_to_delete.append(k)

        for k in keys_to_delete:
            _L1_CACHE.pop(k, None)
