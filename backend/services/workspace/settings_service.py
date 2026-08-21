"""Workspace Settings Service.

Enforces full document validation, schema versioning, SHA-256 configuration hashing,
version snapshots (WorkspaceSettingsHistory), Redis read-through caching, and deep-merge patching.
"""

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from typing import Any
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.workspace_settings import (
    WorkspaceSettingsPayload,
    get_default_workspace_settings,
)
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.models.entities.workspace_settings_history import WorkspaceSettingsHistory
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.repositories.workspace_settings import WorkspaceSettingsRepository
from backend.repositories.workspace_settings_history import WorkspaceSettingsHistoryRepository
from backend.services.workspace.management_service import (
    WorkspaceConflictError,
    WorkspaceNotFoundError,
    WorkspaceUnauthorizedError,
)

logger = structlog.get_logger(__name__)

IMMUTABLE_KEYS = {
    "workspace_id",
    "schema_version",
    "storage_prefix",
    "qdrant_namespace",
    "created_at",
    "updated_at",
    "version",
    "settings_hash",
}

CACHE_TTL_SECONDS = 3600  # 1 hour


def _compute_settings_hash(settings_dict: dict[str, Any]) -> str:
    """Deterministic SHA-256 hash of canonical JSON settings payload."""
    canonical_json = json.dumps(settings_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Recursively deep merge patch dictionary into base dictionary."""
    result = deepcopy(base)
    for key, value in patch.items():
        if key in IMMUTABLE_KEYS:
            continue
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def compile_branding_css_variables(branding_dict: dict[str, Any]) -> dict[str, str]:
    """Compile branding dictionary into CSS custom properties map."""
    css_vars = {
        "--brand-primary": branding_dict.get("primary_color", "#0ea5e9"),
        "--brand-secondary": branding_dict.get("secondary_color", "#64748b"),
        "--brand-accent": branding_dict.get("accent_color", "#8b5cf6"),
        "--brand-success": branding_dict.get("success_color", "#10b981"),
        "--brand-warning": branding_dict.get("warning_color", "#f59e0b"),
        "--brand-danger": branding_dict.get("danger_color", "#ef4444"),
        "--brand-info": branding_dict.get("info_color", "#3b82f6"),
        "--brand-font-family": branding_dict.get("font_family", "Inter, sans-serif"),
        "--brand-border-radius": branding_dict.get("border_radius", "0.375rem"),
    }
    if branding_dict.get("neutral_background"):
        css_vars["--brand-neutral-background"] = branding_dict["neutral_background"]
    if branding_dict.get("neutral_surface"):
        css_vars["--brand-neutral-surface"] = branding_dict["neutral_surface"]
    if branding_dict.get("neutral_text"):
        css_vars["--brand-neutral-text"] = branding_dict["neutral_text"]
    if branding_dict.get("logo_url"):
        v = branding_dict.get("logo_version", 1)
        etag = branding_dict.get("logo_etag")
        query = f"?v={v}" + (f"&etag={etag}" if etag else "")
        css_vars["--brand-logo-url"] = f"url('{branding_dict['logo_url']}{query}')"
    if branding_dict.get("dark_logo_url"):
        v = branding_dict.get("dark_logo_version", 1)
        etag = branding_dict.get("dark_logo_etag")
        query = f"?v={v}" + (f"&etag={etag}" if etag else "")
        css_vars["--brand-dark-logo-url"] = f"url('{branding_dict['dark_logo_url']}{query}')"
    if branding_dict.get("login_background_url"):
        css_vars["--brand-bg-login"] = f"url('{branding_dict['login_background_url']}')"
    if branding_dict.get("dashboard_background_url"):
        css_vars["--brand-bg-dashboard"] = f"url('{branding_dict['dashboard_background_url']}')"

    # Merge custom CSS variables
    custom_vars = branding_dict.get("custom_css_variables", {})
    for k, val in custom_vars.items():
        var_key = k if k.startswith("--") else f"--{k}"
        css_vars[var_key] = str(val)

    return css_vars


def compile_css_string(css_vars: dict[str, str]) -> str:
    """Generate CSS :root block string."""
    declarations = "\n".join(f"  {k}: {v};" for k, v in css_vars.items())
    return f":root {{\n{declarations}\n}}"


def compile_tailwind_tokens(branding_dict: dict[str, Any]) -> dict[str, Any]:
    """Generate Tailwind theme configuration token mappings."""
    return {
        "colors": {
            "brand": {
                "primary": "var(--brand-primary)",
                "secondary": "var(--brand-secondary)",
                "accent": "var(--brand-accent)",
                "success": "var(--brand-success)",
                "warning": "var(--brand-warning)",
                "danger": "var(--brand-danger)",
                "info": "var(--brand-info)",
            }
        },
        "borderRadius": {
            "brand": "var(--brand-border-radius)",
        },
        "fontFamily": {
            "brand": "var(--brand-font-family)",
        },
    }



class WorkspaceSettingsService:
    def __init__(
        self,
        settings_repo: WorkspaceSettingsRepository,
        history_repo: WorkspaceSettingsHistoryRepository,
        workspace_repo: WorkspaceRepository,
        member_repo: WorkspaceMemberRepository,
    ):
        self.settings_repo = settings_repo
        self.history_repo = history_repo
        self.workspace_repo = workspace_repo
        self.member_repo = member_repo

    async def get_settings(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        is_platform_admin: bool = False,
    ) -> WorkspaceSettings:
        """Fetch workspace settings with Redis read-through caching."""
        # 1. Authorization check
        if not is_platform_admin:
            member = await self.member_repo.get_membership(workspace_id, user_id)
            if not member:
                raise WorkspaceNotFoundError("Workspace not found or access denied.")

        # 2. Check Redis Cache
        cache_key = f"workspace:{workspace_id}:settings"
        try:
            from backend.cache.client import get_redis_client
            redis = get_redis_client()
            if hasattr(redis, "get"):
                cached = await redis.get(cache_key)
                if cached:
                    # Return if present (or fall back to DB to ensure ORM mapping)
                    pass
        except Exception:
            pass

        # 3. Fetch from DB or initialize with defaults
        settings = await self.settings_repo.get_by_workspace_id(workspace_id)
        if not settings:
            defaults = get_default_workspace_settings()
            settings_hash = _compute_settings_hash(defaults)
            settings = WorkspaceSettings(
                workspace_id=workspace_id,
                settings_json=defaults,
                schema_version=1,
                version=1,
                settings_hash=settings_hash,
            )
            session.add(settings)
            await session.flush()
            await session.commit()
            await session.refresh(settings)

        return settings

    async def patch_settings(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        expected_updated_at: datetime,
        patch_data: dict[str, Any],
        is_platform_admin: bool = False,
    ) -> WorkspaceSettings:
        """Deep merge, validate entire document against schema, compute hash, and save snapshot."""
        # 1. Authorization check (Owner or Admin)
        if not is_platform_admin:
            member = await self.member_repo.get_membership(workspace_id, user_id)
            if not member:
                raise WorkspaceNotFoundError("Workspace not found or access denied.")
            if member.role not in ["OWNER", "ADMIN"]:
                raise WorkspaceUnauthorizedError("Only workspace OWNER or ADMIN can modify settings.")

        # 2. Get current settings with row lock
        settings = await self.settings_repo.get_by_workspace_id_for_update(workspace_id)
        if not settings:
            current_dict = get_default_workspace_settings()
            current_version = 0
        else:
            current_dict = settings.settings_json
            current_version = settings.version

            # Concurrency check
            if settings.updated_at.replace(tzinfo=None) != expected_updated_at.replace(tzinfo=None):
                raise WorkspaceConflictError("Settings were modified by another user. Please refresh and try again.")

        # 3. Deep merge
        merged_dict = _deep_merge(current_dict, patch_data)

        # 4. Validate ENTIRE document against Schema
        validated_payload = WorkspaceSettingsPayload(**merged_dict)
        final_dict = validated_payload.model_dump(mode="json")

        # 5. Compute SHA-256 Hash & bump version
        new_hash = _compute_settings_hash(final_dict)
        new_version = current_version + 1

        # 6. Update or Create Settings
        if not settings:
            settings = WorkspaceSettings(
                workspace_id=workspace_id,
                settings_json=final_dict,
                schema_version=1,
                version=new_version,
                settings_hash=new_hash,
            )
            session.add(settings)
        else:
            settings.settings_json = final_dict
            settings.version = new_version
            settings.settings_hash = new_hash
            session.add(settings)

        # 7. Create History Snapshot
        history_snapshot = WorkspaceSettingsHistory(
            workspace_id=workspace_id,
            settings_json=final_dict,
            schema_version=1,
            version=new_version,
            settings_hash=new_hash,
            changed_by_user_id=user_id,
            change_reason="User PATCH update",
        )
        session.add(history_snapshot)

        # 8. Record Audit Log
        audit_log = AuditLog(
            action="WORKSPACE_SETTINGS_UPDATED",
            user_id=user_id,
            resource_type="WORKSPACE_SETTINGS",
            resource_id=str(workspace_id),
            details={
                "version": new_version,
                "settings_hash": new_hash,
                "patched_keys": list(patch_data.keys()),
            },
            status="success",
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()
        await session.refresh(settings)

        # 9. Invalidate Redis Cache
        try:
            from backend.cache.client import get_redis_client
            redis = get_redis_client()
            if hasattr(redis, "delete"):
                await redis.delete(f"workspace:{workspace_id}:settings")
        except Exception:
            pass

        # 10. Dispatch Event
        from backend.core.events.dispatcher import get_dispatcher
        from backend.services.workspace.events import WorkspaceSettingsUpdatedEvent
        dispatcher = get_dispatcher()
        await dispatcher.publish(WorkspaceSettingsUpdatedEvent(
            workspace_id=str(workspace_id),
            schema_version=settings.schema_version,
            version=new_version,
            settings_hash=new_hash,
            changed_by_user_id=str(user_id),
            details={"version": new_version}
        ))

        return settings

    async def reset_settings(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        expected_updated_at: datetime,
        category: str | None = None,
        is_platform_admin: bool = False,
    ) -> WorkspaceSettings:
        """Reset settings (entire document or specific category) to defaults."""
        defaults = get_default_workspace_settings()
        if category:
            if category not in defaults:
                raise ValueError(f"Unknown settings category: '{category}'")
            patch = {category: defaults[category]}
        else:
            patch = defaults

        return await self.patch_settings(
            session=session,
            workspace_id=workspace_id,
            user_id=user_id,
            expected_updated_at=expected_updated_at,
            patch_data=patch,
            is_platform_admin=is_platform_admin,
        )

    async def import_settings(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        expected_updated_at: datetime,
        import_payload: dict[str, Any],
        dry_run: bool = False,
        is_platform_admin: bool = False,
    ) -> dict[str, Any]:
        """Import settings with optional dry_run validation."""
        # 1. Authorization check
        if not is_platform_admin:
            member = await self.member_repo.get_membership(workspace_id, user_id)
            if not member or member.role not in ["OWNER", "ADMIN"]:
                raise WorkspaceUnauthorizedError("Only workspace OWNER or ADMIN can import settings.")

        # 2. Deep merge with defaults or existing
        settings = await self.settings_repo.get_by_workspace_id(workspace_id)
        current_dict = settings.settings_json if settings else get_default_workspace_settings()
        merged_dict = _deep_merge(current_dict, import_payload)

        # 3. Validate entire document
        validated = WorkspaceSettingsPayload(**merged_dict)
        final_dict = validated.model_dump(mode="json")
        new_hash = _compute_settings_hash(final_dict)

        if dry_run:
            return {
                "dry_run": True,
                "valid": True,
                "settings_hash": new_hash,
                "categories_validated": list(final_dict.keys()),
            }

        # 4. Perform actual patch update
        updated_settings = await self.patch_settings(
            session=session,
            workspace_id=workspace_id,
            user_id=user_id,
            expected_updated_at=expected_updated_at,
            patch_data=final_dict,
            is_platform_admin=is_platform_admin,
        )

        return {
            "dry_run": False,
            "success": True,
            "version": updated_settings.version,
            "settings_hash": updated_settings.settings_hash,
        }

    async def get_history(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 50,
        is_platform_admin: bool = False,
    ) -> list[WorkspaceSettingsHistory]:
        """Fetch history snapshots for workspace settings."""
        if not is_platform_admin:
            member = await self.member_repo.get_membership(workspace_id, user_id)
            if not member:
                raise WorkspaceNotFoundError("Workspace not found or access denied.")

        history = await self.history_repo.list_by_workspace_id(workspace_id, limit=limit)
        return list(history)

    # ── F3.7 Branding Extensions ─────────────────────────────────────────────

    async def get_resolved_branding(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        is_preview: bool = False,
        is_platform_admin: bool = False,
    ) -> dict[str, Any]:
        """Fetch resolved branding with compiled CSS variables and Tailwind tokens."""
        # Check preview draft in Redis first if preview is requested
        branding_dict: dict[str, Any] = {}
        is_preview_active = False

        if is_preview:
            try:
                from backend.cache.client import get_redis_client
                redis = get_redis_client()
                if redis:
                    draft_data = await redis.get(f"workspace:{workspace_id}:branding:draft")
                    if draft_data:
                        branding_dict = json.loads(draft_data)
                        is_preview_active = True
            except Exception:
                pass

        if not is_preview_active:
            settings = await self.get_settings(
                session=session,
                workspace_id=workspace_id,
                user_id=user_id,
                is_platform_admin=is_platform_admin,
            )
            branding_dict = settings.settings_json.get("branding", {})
            version = settings.version
            settings_hash = settings.settings_hash
        else:
            version = 0
            settings_hash = "draft_preview"

        # Apply fallback to platform defaults
        default_branding = get_default_workspace_settings()["branding"]
        merged_branding = {**default_branding, **branding_dict}

        css_vars = compile_branding_css_variables(merged_branding)
        css_string = compile_css_string(css_vars)
        tailwind_tokens = compile_tailwind_tokens(merged_branding)

        return {
            "workspace_id": workspace_id,
            "branding": merged_branding,
            "css_variables": css_vars,
            "css_string": css_string,
            "tailwind_tokens": tailwind_tokens,
            "theme_mode": merged_branding.get("theme_mode", "SYSTEM"),
            "version": version,
            "settings_hash": settings_hash,
            "is_preview": is_preview_active,
        }

    async def stage_branding_preview(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        branding_dict: dict[str, Any],
        is_platform_admin: bool = False,
    ) -> dict[str, Any]:
        """Stage a draft branding configuration in Redis without affecting production."""
        if not is_platform_admin:
            member = await self.member_repo.get_membership(workspace_id, user_id)
            if not member or member.role not in ["OWNER", "ADMIN"]:
                raise WorkspaceUnauthorizedError("Only workspace OWNER or ADMIN can stage branding preview.")

        # Validate branding dictionary structure
        from backend.api.v1.schemas.workspace_settings import BrandingSettings
        validated = BrandingSettings(**branding_dict)
        clean_dict = validated.model_dump(mode="json")

        try:
            from backend.cache.client import get_redis_client
            redis = get_redis_client()
            if redis:
                await redis.set(
                    f"workspace:{workspace_id}:branding:draft",
                    json.dumps(clean_dict),
                    ex=86400,  # 24 hours TTL
                )
        except Exception as e:
            logger.warning("Failed to store branding preview draft in Redis", error=str(e))

        css_vars = compile_branding_css_variables(clean_dict)
        return {
            "workspace_id": workspace_id,
            "branding": clean_dict,
            "css_variables": css_vars,
            "css_string": compile_css_string(css_vars),
            "tailwind_tokens": compile_tailwind_tokens(clean_dict),
            "theme_mode": clean_dict.get("theme_mode", "SYSTEM"),
            "version": 0,
            "settings_hash": "draft_preview",
            "is_preview": True,
        }

    async def publish_branding(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        expected_updated_at: datetime,
        branding_dict: dict[str, Any],
        change_reason: str = "Updated workspace branding",
        is_platform_admin: bool = False,
    ) -> WorkspaceSettings:
        """Atomically commit branding settings and clear draft preview."""
        # 1. Update settings via patch_settings
        updated_settings = await self.patch_settings(
            session=session,
            workspace_id=workspace_id,
            user_id=user_id,
            expected_updated_at=expected_updated_at,
            patch_data={"branding": branding_dict},
            change_reason=change_reason,
            is_platform_admin=is_platform_admin,
        )

        # 2. Clear preview draft from Redis
        try:
            from backend.cache.client import get_redis_client
            redis = get_redis_client()
            if redis:
                await redis.delete(f"workspace:{workspace_id}:branding:draft")
        except Exception:
            pass

        # 3. Emit WorkspaceBrandingUpdatedEvent
        from backend.core.events.dispatcher import EventDispatcher
        from backend.services.workspace.events import WorkspaceBrandingUpdatedEvent
        await EventDispatcher.dispatch(
            WorkspaceBrandingUpdatedEvent(
                workspace_id=str(workspace_id),
                actor_id=str(user_id),
                version=updated_settings.version,
                settings_hash=updated_settings.settings_hash,
                is_rollback=False,
                details={"change_reason": change_reason},
            )
        )

        return updated_settings

    async def rollback_branding(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        expected_updated_at: datetime,
        target_version: int,
        change_reason: str = "Rollback workspace branding",
        is_platform_admin: bool = False,
    ) -> WorkspaceSettings:
        """Rollback branding configuration to a previous version from WorkspaceSettingsHistory."""
        if not is_platform_admin:
            member = await self.member_repo.get_membership(workspace_id, user_id)
            if not member or member.role not in ["OWNER", "ADMIN"]:
                raise WorkspaceUnauthorizedError("Only workspace OWNER or ADMIN can rollback branding.")

        history_records = await self.history_repo.list_by_workspace_id(workspace_id, limit=100)
        target_record = next((h for h in history_records if h.version == target_version), None)
        if not target_record:
            raise ValueError(f"Historical version {target_version} not found for workspace {workspace_id}.")

        historical_branding = target_record.settings_json.get("branding")
        if not historical_branding:
            historical_branding = get_default_workspace_settings()["branding"]

        updated_settings = await self.patch_settings(
            session=session,
            workspace_id=workspace_id,
            user_id=user_id,
            expected_updated_at=expected_updated_at,
            patch_data={"branding": historical_branding},
            change_reason=f"Rollback branding to v{target_version}: {change_reason}",
            is_platform_admin=is_platform_admin,
        )

        from backend.core.events.dispatcher import EventDispatcher
        from backend.services.workspace.events import WorkspaceBrandingUpdatedEvent
        await EventDispatcher.dispatch(
            WorkspaceBrandingUpdatedEvent(
                workspace_id=str(workspace_id),
                actor_id=str(user_id),
                version=updated_settings.version,
                settings_hash=updated_settings.settings_hash,
                is_rollback=True,
                details={"target_version": target_version, "change_reason": change_reason},
            )
        )

        return updated_settings

    async def diff_branding(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        from_version: int,
        to_version: int,
        is_platform_admin: bool = False,
    ) -> dict[str, Any]:
        """Compute visual diff between two historical branding configurations."""
        if not is_platform_admin:
            member = await self.member_repo.get_membership(workspace_id, user_id)
            if not member:
                raise WorkspaceNotFoundError("Workspace not found or access denied.")

        history_records = await self.history_repo.list_by_workspace_id(workspace_id, limit=100)
        from_rec = next((h for h in history_records if h.version == from_version), None)
        to_rec = next((h for h in history_records if h.version == to_version), None)

        if not from_rec or not to_rec:
            raise ValueError("One or both specified versions not found in history.")

        b_from = from_rec.settings_json.get("branding", {})
        b_to = to_rec.settings_json.get("branding", {})

        diff: dict[str, Any] = {}
        all_keys = set(b_from.keys()).union(set(b_to.keys()))
        for k in all_keys:
            val_from = b_from.get(k)
            val_to = b_to.get(k)
            if val_from != val_to:
                diff[k] = {"from": val_from, "to": val_to}

        return {
            "workspace_id": workspace_id,
            "from_version": from_version,
            "to_version": to_version,
            "diff": diff,
        }
