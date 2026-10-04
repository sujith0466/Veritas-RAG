from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import re
import secrets
from typing import Any
import uuid

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.workspace_onboarding import (
    CROCKFORD_ALPHABET,
    JOIN_CODE_PATTERN,
    JoinCodeGenerateResponse,
    JoinCodeSettingsPatchRequest,
    JoinCodeSettingsSchema,
)
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.workspace import WorkspaceStatus
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.models.entities.workspace_settings_history import WorkspaceSettingsHistory
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.repositories.workspace_settings import WorkspaceSettingsRepository
from backend.services.workspace.management_service import (
    WorkspaceNotFoundError,
    WorkspaceUnauthorizedError,
)

logger = structlog.get_logger(__name__)


def _compute_settings_hash(settings_dict: dict[str, Any]) -> str:
    canonical_json = json.dumps(settings_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class JoinCodeService:
    """Canonical service for Join Code lifecycle, cryptographic hashing, and safe persistence.

    SECURITY INVARIANTS:
    1. Plaintext Join Code (VR-XXXXXX) is NEVER persisted in PostgreSQL or Redis.
    2. Plaintext is returned strictly once upon generation/regeneration in JoinCodeGenerateResponse.
    3. Stored credential is a salted, slow bcrypt hash (cost factor 12) resistant to offline brute-force attacks.
    4. Plaintext or hash is NEVER recorded in audit logs, error messages, or exception traces.
    5. Default role is strictly limited to 'MEMBER' or 'VIEWER'; elevated roles ('OWNER', 'ADMIN') are rejected.
    """

    ALLOWED_ROLES = {"MEMBER", "VIEWER"}
    DEFAULT_EXPIRATION_DAYS = 30
    BCRYPT_ROUNDS = 12

    def __init__(
        self,
        settings_repo: WorkspaceSettingsRepository,
        member_repo: WorkspaceMemberRepository,
        workspace_repo: WorkspaceRepository,
    ):
        self.settings_repo = settings_repo
        self.member_repo = member_repo
        self.workspace_repo = workspace_repo

    # ── Cryptographic Primitives ───────────────────────────────────────────────

    @classmethod
    def generate_plaintext_code(cls) -> str:
        """Generates a cryptographically random 6-character Crockford Base32 join code."""
        entropy = "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(6))
        code = f"VR-{entropy}"
        if not re.match(JOIN_CODE_PATTERN, code):
            raise RuntimeError("Cryptographic PRNG generated an invalid join code shape.")
        return code

    @classmethod
    def hash_join_code(cls, code: str, rounds: int = BCRYPT_ROUNDS) -> str:
        """Computes salted, adaptive bcrypt hash of normalized join code.

        Protects the 32^6 (~1.07B) keyspace against practical offline rainbow table
        and brute-force enumeration by enforcing a slow, memory-hard adaptive KDF.
        """
        clean = code.strip().upper()
        if not re.match(JOIN_CODE_PATTERN, clean):
            raise ValueError(f"Malformed join code '{code}'. Expected 'VR-XXXXXX' format.")
        salt = bcrypt.gensalt(rounds=rounds)
        return bcrypt.hashpw(clean.encode("utf-8"), salt).decode("utf-8")

    @classmethod
    def is_legacy_sha256_hash(cls, stored_hash: str | None) -> bool:
        """Returns True if the stored verifier is in legacy 64-character SHA-256 hex format."""
        if not stored_hash or len(stored_hash) != 64:
            return False
        return bool(re.match(r"^[a-f0-9]{64}$", stored_hash, re.IGNORECASE))

    @classmethod
    def verify_join_code(cls, candidate_code: str, stored_hash: str) -> bool:
        """Verifies candidate join code against stored hash using constant-time verification.

        Supports:
        1. Primary: Salted bcrypt hash ($2a$, $2b$, $2y$).
        2. Backward-compatibility: Legacy SHA-256 hex digest verified with hmac.compare_digest.
        """
        if not candidate_code or not stored_hash:
            return False

        clean = candidate_code.strip().upper()
        if not re.match(JOIN_CODE_PATTERN, clean):
            return False

        # Primary: Salted bcrypt verification
        if stored_hash.startswith(("$2a$", "$2b$", "$2y$")):
            try:
                return bcrypt.checkpw(clean.encode("utf-8"), stored_hash.encode("utf-8"))
            except (ValueError, TypeError):
                return False

        # Backward compatibility: Legacy SHA-256 verification
        if cls.is_legacy_sha256_hash(stored_hash):
            candidate_hash = hashlib.sha256(clean.encode("utf-8")).hexdigest()
            return hmac.compare_digest(candidate_hash, stored_hash.lower())

        return False

    # ── Authorization Guard ───────────────────────────────────────────────────

    async def _verify_actor_authority(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        is_platform_admin: bool = False,
    ) -> None:
        """Enforces that actor is an OWNER or ADMIN within the target workspace boundary."""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace or workspace.status != WorkspaceStatus.ACTIVE.value:
            raise WorkspaceNotFoundError("Workspace not found or inactive.")

        if is_platform_admin:
            return

        member = await self.member_repo.get_membership(workspace_id, user_id)
        if not member:
            raise WorkspaceNotFoundError("Workspace not found or access denied.")

        if member.role not in ["OWNER", "ADMIN"]:
            raise WorkspaceUnauthorizedError("Only workspace OWNER or ADMIN can manage join code settings.")

    # ── Redis Cache Invalidation ──────────────────────────────────────────────

    async def _invalidate_settings_cache(self, workspace_id: uuid.UUID) -> None:
        """Invalidates workspace settings Redis cache on join code mutation."""
        cache_key = f"workspace:{workspace_id}:settings"
        try:
            from backend.cache.client import get_redis_client
            redis = get_redis_client()
            if hasattr(redis, "delete"):
                await redis.delete(cache_key)
        except Exception:
            pass

    # ── Settings Retrieval ────────────────────────────────────────────────────

    async def get_join_code_settings(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        is_platform_admin: bool = False,
    ) -> JoinCodeSettingsSchema:
        """Fetches safe join code configuration state. Plaintext and hash are NEVER returned."""
        await self._verify_actor_authority(workspace_id, user_id, is_platform_admin)

        settings = await self.settings_repo.get_by_workspace_id(workspace_id)
        config: dict[str, Any] = {}
        if settings and settings.settings_json:
            config = settings.settings_json.get("join_code", {})

        code_hash = config.get("code_hash")
        expires_at_val = config.get("expires_at")
        generated_at_val = config.get("generated_at")
        generated_by_val = config.get("generated_by")

        expires_at = datetime.fromisoformat(expires_at_val) if expires_at_val else None
        generated_at = datetime.fromisoformat(generated_at_val) if generated_at_val else None
        generated_by = uuid.UUID(generated_by_val) if generated_by_val else None

        return JoinCodeSettingsSchema(
            enabled=bool(config.get("is_enabled", False)),
            default_role=config.get("default_role", "MEMBER"),
            require_approval=bool(config.get("require_approval", False)),
            expires_at=expires_at,
            generated_at=generated_at,
            generated_by=generated_by,
            has_code=bool(code_hash),
            max_uses=config.get("max_uses"),
            current_uses=config.get("current_uses", 0),
        )

    # ── Settings Mutation ─────────────────────────────────────────────────────

    async def patch_join_code_settings(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        request: JoinCodeSettingsPatchRequest,
        is_platform_admin: bool = False,
    ) -> JoinCodeSettingsSchema:
        """Patches join code administrative settings (enabled, role, approval, max uses)."""
        await self._verify_actor_authority(workspace_id, user_id, is_platform_admin)

        if request.default_role is not None and request.default_role not in self.ALLOWED_ROLES:
            raise ValueError(f"Default role must be 'MEMBER' or 'VIEWER', got '{request.default_role}'.")

        settings = await self.settings_repo.get_by_workspace_id_for_update(workspace_id)
        if not settings:
            settings = WorkspaceSettings(
                workspace_id=workspace_id,
                settings_json={},
                schema_version=1,
                version=1,
                settings_hash="",
            )
            session.add(settings)
            await session.flush()

        settings_dict = dict(settings.settings_json or {})
        join_code_config = dict(settings_dict.get("join_code", {}))

        if request.enabled is not None:
            join_code_config["is_enabled"] = request.enabled
        if request.default_role is not None:
            join_code_config["default_role"] = request.default_role
        if request.require_approval is not None:
            join_code_config["require_approval"] = request.require_approval
        if request.max_uses is not None:
            join_code_config["max_uses"] = request.max_uses

        settings_dict["join_code"] = join_code_config
        settings.settings_json = settings_dict
        settings.version += 1
        settings.settings_hash = _compute_settings_hash(settings_dict)

        # Audit log entry without sensitive data
        audit_log = AuditLog(
            tenant_id=workspace_id,
            action="JOIN_CODE_SETTINGS_UPDATED",
            user_id=user_id,
            resource_type="WORKSPACE_JOIN_CODE",
            resource_id=str(workspace_id),
            details={
                "enabled": join_code_config.get("is_enabled"),
                "default_role": join_code_config.get("default_role"),
                "require_approval": join_code_config.get("require_approval"),
            },
            status="success",
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()
        await session.refresh(settings)

        await self._invalidate_settings_cache(workspace_id)

        return await self.get_join_code_settings(session, workspace_id, user_id, is_platform_admin)

    # ── Generation & Regeneration ─────────────────────────────────────────────

    async def generate_new_join_code(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        is_platform_admin: bool = False,
        expires_in_days: int = DEFAULT_EXPIRATION_DAYS,
        default_role: str = "MEMBER",
        require_approval: bool = False,
        max_uses: int | None = None,
        is_regeneration: bool = False,
    ) -> JoinCodeGenerateResponse:
        """Generates or regenerates a workspace Join Code.

        The plaintext code is returned strictly once in this response and is NEVER persisted.
        """
        await self._verify_actor_authority(workspace_id, user_id, is_platform_admin)

        role_clean = default_role.strip().upper()
        if role_clean not in self.ALLOWED_ROLES:
            raise ValueError(f"Default role must be 'MEMBER' or 'VIEWER', got '{default_role}'.")

        # 1. Cryptographically generate plaintext code and SHA-256 hash
        plaintext_code = self.generate_plaintext_code()
        code_hash = self.hash_join_code(plaintext_code)

        # 2. Compute expiration
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=expires_in_days) if expires_in_days > 0 else None

        # 3. Retrieve settings with row-level lock
        settings = await self.settings_repo.get_by_workspace_id_for_update(workspace_id)
        if not settings:
            settings = WorkspaceSettings(
                workspace_id=workspace_id,
                settings_json={},
                schema_version=1,
                version=1,
                settings_hash="",
            )
            session.add(settings)
            await session.flush()

        settings_dict = dict(settings.settings_json or {})
        existing_join_config = settings_dict.get("join_code", {})

        # 4. Invalidate prior code immediately and store new hash-only configuration
        new_join_config = {
            "is_enabled": True,
            "code_hash": code_hash,
            "default_role": existing_join_config.get("default_role", role_clean),
            "require_approval": existing_join_config.get("require_approval", require_approval),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "generated_at": now.isoformat(),
            "generated_by": str(user_id),
            "max_uses": max_uses,
            "current_uses": 0,
        }

        settings_dict["join_code"] = new_join_config
        settings.settings_json = settings_dict
        settings.version += 1
        settings.settings_hash = _compute_settings_hash(settings_dict)

        # 5. Snapshot to history table
        history_entry = WorkspaceSettingsHistory(
            workspace_id=workspace_id,
            version=settings.version,
            settings_json=settings_dict,
            settings_hash=settings.settings_hash,
            changed_by_user_id=user_id,
            change_reason="JOIN_CODE_REGENERATED" if is_regeneration else "JOIN_CODE_GENERATED",
        )
        session.add(history_entry)

        # 6. Audit log entry with non-secret metadata
        audit_log = AuditLog(
            tenant_id=workspace_id,
            action="JOIN_CODE_REGENERATED" if is_regeneration else "JOIN_CODE_GENERATED",
            user_id=user_id,
            resource_type="WORKSPACE_JOIN_CODE",
            resource_id=str(workspace_id),
            details={
                "expires_at": expires_at.isoformat() if expires_at else None,
                "default_role": new_join_config["default_role"],
                "has_code": True,
            },
            status="success",
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()
        await session.refresh(settings)

        await self._invalidate_settings_cache(workspace_id)

        # 7. Reveal plaintext strictly once
        return JoinCodeGenerateResponse(
            success=True,
            join_code=plaintext_code,
            expires_at=expires_at,
            default_role=new_join_config["default_role"],
            warning=(
                "This Join Code will only be displayed once. Copy and share it with your team now. "
                "Veritas-RAG stores only a cryptographic hash and cannot retrieve this code later."
            ),
        )

    # ── Candidate Validation Service ──────────────────────────────────────────

    async def validate_join_code_candidate(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        candidate_code: str,
    ) -> tuple[bool, str | None, str]:
        """Validates a candidate join code against stored workspace settings.

        Returns: (is_valid, error_reason, default_role)
        """
        if not candidate_code or not isinstance(candidate_code, str):
            return False, "Invalid join code format.", ""

        clean = candidate_code.strip().upper()
        if not re.match(JOIN_CODE_PATTERN, clean):
            return False, "Invalid join code format. Expected 'VR-XXXXXX'.", ""

        settings = await self.settings_repo.get_by_workspace_id(workspace_id)
        if not settings or not settings.settings_json:
            return False, "Workspace settings not found.", ""

        config = settings.settings_json.get("join_code", {})
        if not config.get("is_enabled", False):
            return False, "Join Code entry is currently disabled for this workspace.", ""

        stored_hash = config.get("code_hash")
        if not stored_hash:
            return False, "No active join code configured.", ""

        # Check expiration
        expires_at_str = config.get("expires_at")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.now(UTC) >= expires_at:
                    return False, "Join code has expired.", ""
            except (ValueError, TypeError):
                return False, "Invalid expiration format in stored configuration.", ""

        # Check usage limits
        max_uses = config.get("max_uses")
        current_uses = config.get("current_uses", 0)
        if max_uses is not None and current_uses >= max_uses:
            return False, "Join code usage limit has been reached.", ""

        # Constant-time cryptographic verification
        if not self.verify_join_code(clean, stored_hash):
            return False, "Invalid join code.", ""

        # Transparent upgrade from legacy SHA-256 to salted slow bcrypt verifier
        if self.is_legacy_sha256_hash(stored_hash):
            try:
                upgraded_hash = self.hash_join_code(clean)
                settings_for_update = await self.settings_repo.get_by_workspace_id_for_update(workspace_id)
                if settings_for_update and settings_for_update.settings_json:
                    settings_dict = dict(settings_for_update.settings_json)
                    jc = dict(settings_dict.get("join_code", {}))
                    jc["code_hash"] = upgraded_hash
                    settings_dict["join_code"] = jc
                    settings_for_update.settings_json = settings_dict
                    settings_for_update.version += 1
                    settings_for_update.settings_hash = _compute_settings_hash(settings_dict)
                    session.add(settings_for_update)
                    await session.flush()
                    await session.commit()
                    await self._invalidate_settings_cache(workspace_id)
                    logger.info(
                        "Transparently upgraded legacy join code hash to salted slow verifier",
                        workspace_id=str(workspace_id),
                    )
            except Exception as e:
                logger.warning(
                    "Failed to transparently upgrade legacy join code hash",
                    workspace_id=str(workspace_id),
                    error=str(e),
                )

        default_role = config.get("default_role", "MEMBER")
        return True, None, default_role
