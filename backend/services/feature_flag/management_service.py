"""Feature Flag Management Service.

Handles administrative lifecycle management, workspace rule overrides,
emergency kill switches, version snapshots, and point-in-time rollbacks.
"""

from collections.abc import Sequence
from datetime import datetime, timezone
import json
import time
from typing import Any
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.events.dispatcher import get_dispatcher
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.feature_flag import (
    FeatureFlag,
    FlagCategory,
    FlagLifecycleState,
    FlagType,
)
from backend.models.entities.feature_flag_history import FeatureFlagHistory
from backend.models.entities.feature_flag_workspace_rule import FeatureFlagWorkspaceRule
from backend.observability.metrics.prometheus import set_active_killswitches_count
from backend.repositories.feature_flag import (
    FeatureFlagHistoryRepository,
    FeatureFlagRepository,
    FeatureFlagWorkspaceRuleRepository,
)
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.services.feature_flag.evaluation_service import (
    FeatureFlagEvaluationService,
    validate_no_circular_dependencies,
)
from backend.services.feature_flag.events import (
    FeatureFlagCreatedEvent,
    FeatureFlagKillswitchTriggeredEvent,
    FeatureFlagRuleUpdatedEvent,
    FeatureFlagUpdatedEvent,
)
from backend.services.workspace.management_service import (
    WorkspaceConflictError,
    WorkspaceNotFoundError,
    WorkspaceUnauthorizedError,
)

logger = structlog.get_logger(__name__)


class FeatureFlagManagementService:
    """Enterprise management service for feature flags and rules."""

    def __init__(
        self,
        flag_repo: FeatureFlagRepository,
        rule_repo: FeatureFlagWorkspaceRuleRepository,
        history_repo: FeatureFlagHistoryRepository,
        workspace_repo: WorkspaceRepository,
        member_repo: WorkspaceMemberRepository,
    ) -> None:
        self.flag_repo = flag_repo
        self.rule_repo = rule_repo
        self.history_repo = history_repo
        self.workspace_repo = workspace_repo
        self.member_repo = member_repo

    async def _invalidate_cache(self, flag_key: str, workspace_id: uuid.UUID | None = None) -> None:
        """Invalidate L1 memory cache and L2 Redis cache, broadcasting over Pub/Sub."""
        FeatureFlagEvaluationService.invalidate_local_cache(workspace_id=workspace_id, flag_key=flag_key)
        try:
            from backend.cache.client import get_redis_client
            redis = get_redis_client()
            if redis:
                if workspace_id:
                    await redis.delete(f"ff:ws:{workspace_id}:{flag_key}")
                else:
                    # Invalidate all keys matching flag
                    keys = await redis.keys(f"ff:ws:*:{flag_key}")
                    if keys:
                        await redis.delete(*keys)
                # Broadcast invalidation event
                await redis.publish(
                    "raguard:events:feature_flags",
                    json.dumps({
                        "flag_key": flag_key,
                        "workspace_id": str(workspace_id) if workspace_id else None,
                        "timestamp": time.time(),
                    }),
                )
        except Exception as e:
            logger.warning("Failed to broadcast feature flag cache invalidation", error=str(e))

    # ── 1. Master Flag Operations (Platform Admin) ───────────────────────────

    async def create_flag(
        self,
        session: AsyncSession,
        actor_id: uuid.UUID,
        key: str,
        name: str,
        description: str | None = None,
        category: FlagCategory = FlagCategory.SYSTEM,
        lifecycle_state: FlagLifecycleState = FlagLifecycleState.DRAFT,
        flag_type: FlagType = FlagType.BOOLEAN,
        default_enabled: bool = False,
        prerequisite_flag_keys: list[str] | None = None,
        default_variant_json: dict[str, Any] | None = None,
        target_environments: str = "production,staging,development",
        change_reason: str = "Initial flag creation",
    ) -> FeatureFlag:
        """Create a new master feature flag."""
        clean_key = key.strip().lower()
        existing = await self.flag_repo.get_by_key(clean_key)
        if existing:
            raise ValueError(f"Feature flag with key '{clean_key}' already exists.")

        prereqs = prerequisite_flag_keys or []
        if prereqs:
            # Build graph and check circular dependency
            all_flags = await self.flag_repo.list_active_flags()
            graph = {f.key: f.prerequisite_flag_keys for f in all_flags}
            validate_no_circular_dependencies(clean_key, prereqs, graph)

        flag = await self.flag_repo.create(
            key=clean_key,
            name=name,
            description=description,
            category=category.value if isinstance(category, FlagCategory) else category,
            lifecycle_state=lifecycle_state.value if isinstance(lifecycle_state, FlagLifecycleState) else lifecycle_state,
            flag_type=flag_type.value if isinstance(flag_type, FlagType) else flag_type,
            default_enabled=default_enabled,
            is_killswitch_active=False,
            prerequisite_flag_keys=prereqs,
            default_variant_json=default_variant_json or {},
            target_environments=target_environments,
            version=1,
        )

        # Snapshot history
        await self.history_repo.create(
            flag_id=flag.id,
            workspace_id=None,
            changed_by_user_id=actor_id,
            version=1,
            change_action="CREATE_FLAG",
            change_reason=change_reason,
            old_rule_json=None,
            new_rule_json=flag.to_dict(),
        )

        # Audit Log
        audit = AuditLog(
            action="FEATURE_FLAG_CREATED",
            resource_type="FEATURE_FLAG",
            resource_id=str(flag.id),
            user_id=actor_id,
            details={"key": clean_key, "name": name, "category": flag.category},
            status="success",
        )
        session.add(audit)
        await session.flush()

        await get_dispatcher().publish(
            FeatureFlagCreatedEvent(
                flag_key=clean_key,
                actor_id=str(actor_id),
                category=flag.category,
                details={"reason": change_reason},
            )
        )

        return flag

    async def update_flag(
        self,
        session: AsyncSession,
        actor_id: uuid.UUID,
        key: str,
        name: str | None = None,
        description: str | None = None,
        category: FlagCategory | None = None,
        lifecycle_state: FlagLifecycleState | None = None,
        default_enabled: bool | None = None,
        prerequisite_flag_keys: list[str] | None = None,
        default_variant_json: dict[str, Any] | None = None,
        target_environments: str | None = None,
        change_reason: str = "Updated feature flag configuration",
    ) -> FeatureFlag:
        """Update a master feature flag definition."""
        flag = await self.flag_repo.get_by_key_for_update(key)
        if not flag:
            raise ValueError(f"Feature flag '{key}' not found.")

        old_snapshot = flag.to_dict()

        if prerequisite_flag_keys is not None:
            all_flags = await self.flag_repo.list_active_flags()
            graph = {f.key: f.prerequisite_flag_keys for f in all_flags if f.key != key}
            validate_no_circular_dependencies(key, prerequisite_flag_keys, graph)
            flag.prerequisite_flag_keys = prerequisite_flag_keys

        if name is not None:
            flag.name = name
        if description is not None:
            flag.description = description
        if category is not None:
            flag.category = category.value if isinstance(category, FlagCategory) else category
        if lifecycle_state is not None:
            flag.lifecycle_state = (
                lifecycle_state.value if isinstance(lifecycle_state, FlagLifecycleState) else lifecycle_state
            )
        if default_enabled is not None:
            flag.default_enabled = default_enabled
        if default_variant_json is not None:
            flag.default_variant_json = default_variant_json
        if target_environments is not None:
            flag.target_environments = target_environments

        flag.version += 1
        flag.updated_at = datetime.now(timezone.utc)
        await session.flush()

        # Snapshot history
        await self.history_repo.create(
            flag_id=flag.id,
            workspace_id=None,
            changed_by_user_id=actor_id,
            version=flag.version,
            change_action="UPDATE_FLAG",
            change_reason=change_reason,
            old_rule_json=old_snapshot,
            new_rule_json=flag.to_dict(),
        )

        await self._invalidate_cache(flag.key)

        await get_dispatcher().publish(
            FeatureFlagUpdatedEvent(
                flag_key=flag.key,
                actor_id=str(actor_id),
                version=flag.version,
                details={"reason": change_reason},
            )
        )

        return flag

    async def toggle_killswitch(
        self,
        session: AsyncSession,
        actor_id: uuid.UUID,
        key: str,
        is_active: bool,
        reason: str = "Emergency kill switch toggle",
    ) -> FeatureFlag:
        """Instantly engage or disengage emergency kill switch."""
        flag = await self.flag_repo.get_by_key_for_update(key)
        if not flag:
            raise ValueError(f"Feature flag '{key}' not found.")

        old_snapshot = flag.to_dict()
        flag.is_killswitch_active = is_active
        flag.version += 1
        flag.updated_at = datetime.now(timezone.utc)
        await session.flush()

        # Snapshot history
        await self.history_repo.create(
            flag_id=flag.id,
            workspace_id=None,
            changed_by_user_id=actor_id,
            version=flag.version,
            change_action="KILLSWITCH_ACTIVATED" if is_active else "KILLSWITCH_DEACTIVATED",
            change_reason=reason,
            old_rule_json=old_snapshot,
            new_rule_json=flag.to_dict(),
        )

        await self._invalidate_cache(flag.key)

        all_flags = await self.flag_repo.list_active_flags()
        active_ks_count = sum(1 for f in all_flags if f.is_killswitch_active)
        set_active_killswitches_count(active_ks_count)

        await get_dispatcher().publish(
            FeatureFlagKillswitchTriggeredEvent(
                flag_key=flag.key,
                actor_id=str(actor_id),
                is_active=is_active,
                reason=reason,
            )
        )

        return flag

    # ── 2. Workspace Override Rules ──────────────────────────────────────────

    async def set_workspace_rule(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        key: str,
        is_enabled: bool = True,
        rollout_percentage: int = 100,
        activation_start_at: datetime | None = None,
        activation_end_at: datetime | None = None,
        targeting_conditions: list[dict[str, Any]] | None = None,
        custom_variant: dict[str, Any] | None = None,
        change_reason: str = "Configured workspace feature flag rule",
        is_platform_admin: bool = False,
    ) -> FeatureFlagWorkspaceRule:
        """Configure or update a workspace-specific feature flag override rule."""
        if not is_platform_admin:
            member = await self.member_repo.get_membership(workspace_id, actor_id)
            if not member or member.role not in ["OWNER", "ADMIN"]:
                raise WorkspaceUnauthorizedError("Only workspace OWNER or ADMIN can configure feature flags.")

        flag = await self.flag_repo.get_by_key(key)
        if not flag:
            raise ValueError(f"Feature flag '{key}' not found.")

        if rollout_percentage < 0 or rollout_percentage > 100:
            raise ValueError("Rollout percentage must be between 0 and 100.")

        rule = await self.rule_repo.get_by_flag_and_workspace_for_update(flag.id, workspace_id)
        old_snapshot = rule.to_dict() if rule else None

        if rule:
            rule.is_enabled = is_enabled
            rule.rollout_percentage = rollout_percentage
            rule.activation_start_at = activation_start_at
            rule.activation_end_at = activation_end_at
            rule.targeting_conditions_json = targeting_conditions or []
            rule.custom_variant_json = custom_variant or {}
            rule.version += 1
            rule.updated_at = datetime.now(timezone.utc)
            await session.flush()
        else:
            rule = await self.rule_repo.create(
                flag_id=flag.id,
                workspace_id=workspace_id,
                is_enabled=is_enabled,
                rollout_percentage=rollout_percentage,
                activation_start_at=activation_start_at,
                activation_end_at=activation_end_at,
                targeting_conditions_json=targeting_conditions or [],
                custom_variant_json=custom_variant or {},
                version=1,
            )

        # Snapshot history
        await self.history_repo.create(
            flag_id=flag.id,
            workspace_id=workspace_id,
            changed_by_user_id=actor_id,
            version=rule.version,
            change_action="SET_WORKSPACE_RULE",
            change_reason=change_reason,
            old_rule_json=old_snapshot,
            new_rule_json=rule.to_dict(),
        )

        await self._invalidate_cache(flag.key, workspace_id=workspace_id)

        await get_dispatcher().publish(
            FeatureFlagRuleUpdatedEvent(
                flag_key=flag.key,
                workspace_id=str(workspace_id),
                actor_id=str(actor_id),
                version=rule.version,
                is_enabled=rule.is_enabled,
                rollout_percentage=rule.rollout_percentage,
                details={"reason": change_reason},
            )
        )

        return rule

    async def delete_workspace_rule(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        actor_id: uuid.UUID,
        key: str,
        change_reason: str = "Deleted workspace override rule",
        is_platform_admin: bool = False,
    ) -> None:
        """Delete a workspace override rule, reverting to global default."""
        if not is_platform_admin:
            member = await self.member_repo.get_membership(workspace_id, actor_id)
            if not member or member.role not in ["OWNER", "ADMIN"]:
                raise WorkspaceUnauthorizedError("Only workspace OWNER or ADMIN can delete feature flag rules.")

        flag = await self.flag_repo.get_by_key(key)
        if not flag:
            raise ValueError(f"Feature flag '{key}' not found.")

        rule = await self.rule_repo.get_by_flag_and_workspace_for_update(flag.id, workspace_id)
        if not rule:
            return

        old_snapshot = rule.to_dict()
        await self.rule_repo.hard_delete(rule)

        # Snapshot history
        await self.history_repo.create(
            flag_id=flag.id,
            workspace_id=workspace_id,
            changed_by_user_id=actor_id,
            version=rule.version + 1,
            change_action="DELETE_WORKSPACE_RULE",
            change_reason=change_reason,
            old_rule_json=old_snapshot,
            new_rule_json={"deleted": True},
        )

        await self._invalidate_cache(flag.key, workspace_id=workspace_id)

    async def get_history(
        self,
        flag_key: str,
        workspace_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> Sequence[FeatureFlagHistory]:
        """Fetch audit history records for a flag."""
        flag = await self.flag_repo.get_by_key(flag_key)
        if not flag:
            raise ValueError(f"Feature flag '{flag_key}' not found.")

        return await self.history_repo.list_history_for_flag(
            flag_id=flag.id, workspace_id=workspace_id, limit=limit
        )
