import base64
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import os
import re
import secrets
from typing import Any, Sequence
import uuid

import bcrypt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.workspace_join_code import (
    MemberAccessStatusEnum,
    MemberJoinAccessResponse,
)
from backend.api.v1.schemas.workspace_onboarding import (
    CROCKFORD_ALPHABET,
    JOIN_CODE_PATTERN,
    JoinCodeGenerateResponse,
    JoinCodeSettingsPatchRequest,
    JoinCodeSettingsSchema,
    WorkspaceJoinAccessResponse,
)
from backend.core.config import get_settings
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.user import User
from backend.models.entities.workspace import WorkspaceStatus
from backend.models.entities.workspace_join_code import (
    WorkspaceJoinCode,
    WorkspaceJoinCodeRedemption,
)
from backend.models.entities.workspace_member import MemberStatus
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.models.entities.workspace_settings_history import WorkspaceSettingsHistory
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_join_code import WorkspaceJoinCodeRepository
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

    SECURITY INVARIANTS (Master Plan Version 2.6):
    1. Plaintext Join Code (VR-XXXXXX) is NEVER persisted in PostgreSQL or Redis.
    2. Plaintext is returned strictly once upon generation/regeneration in JoinCodeGenerateResponse.
    3. Stored secret uses authenticated AES-256-GCM encryption with 96-bit nonce.
    4. Deterministic candidate lookup uses dual-pepper HMAC-SHA256 (primary v2, fallback v1).
    5. Plaintext or hash is NEVER recorded in audit logs, error messages, or exception traces.
    6. Default role is strictly limited to 'MEMBER'; elevated or legacy roles are rejected.
    7. Independent per-creator join codes: each OWNER and ADMIN manages their own active code (Decision Q1).
    8. Unlimited redemptions: use_count is an analytics metric, not a barrier (Decision Q3).
    9. Protected File #5 strictly preserved at 0-bit drift (Decision Q5 Option B; C1 BLOCKED).
    """

    ALLOWED_ROLES = {"MEMBER"}
    DEFAULT_EXPIRATION_DAYS = 30
    BCRYPT_ROUNDS = 12

    PEPPER_V1 = os.environ.get("JOIN_CODE_PEPPER_V1", "raguard-hmac-pepper-v1-fallback-salt")
    PEPPER_V2 = os.environ.get("JOIN_CODE_PEPPER_V2", "raguard-hmac-pepper-v2-primary-salt")

    def __init__(
        self,
        settings_repo: WorkspaceSettingsRepository,
        member_repo: WorkspaceMemberRepository,
        workspace_repo: WorkspaceRepository,
        join_code_repo: WorkspaceJoinCodeRepository | None = None,
    ):
        self.settings_repo = settings_repo
        self.member_repo = member_repo
        self.workspace_repo = workspace_repo
        self.join_code_repo = join_code_repo or WorkspaceJoinCodeRepository()

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
        """Computes salted, adaptive bcrypt hash of normalized join code (for legacy verification)."""
        clean = code.strip().upper()
        if not re.match(JOIN_CODE_PATTERN, clean):
            raise ValueError(f"Malformed join code '{code}'. Expected 'VR-XXXXXX' format.")
        salt = bcrypt.gensalt(rounds=rounds)
        return bcrypt.hashpw(clean.encode("utf-8"), salt).decode("utf-8")

    @classmethod
    def compute_candidate_hash(
        cls,
        code: str,
        pepper_version: str = "v2",
        workspace_id: uuid.UUID | None = None,
    ) -> str:
        """Computes deterministic HMAC-SHA256 candidate lookup hash with tenant isolation."""
        clean = code.strip().upper()
        pepper = cls.PEPPER_V2 if pepper_version == "v2" else cls.PEPPER_V1
        tenant_salt = str(workspace_id) if workspace_id else ""
        key = (pepper + tenant_salt).encode("utf-8")
        return hmac.new(key, clean.encode("utf-8"), hashlib.sha256).hexdigest()

    @classmethod
    def is_legacy_sha256_hash(cls, stored_hash: str | None) -> bool:
        """Returns True if the stored verifier is in legacy 64-character SHA-256 hex format."""
        if not stored_hash or len(stored_hash) != 64:
            return False
        return bool(re.match(r"^[a-f0-9]{64}$", stored_hash, re.IGNORECASE))

    @classmethod
    def verify_join_code(cls, candidate_code: str, stored_hash: str) -> bool:
        """Verifies candidate join code against stored hash using constant-time verification."""
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

    @classmethod
    def _get_aes_key(cls) -> bytes:
        """Derives a deterministic 256-bit (32-byte) key for AES-256-GCM authenticated encryption."""
        try:
            secret = get_settings().app.secret_key
        except Exception:
            secret = "raguard-default-dev-secret-key-32b"
        return hashlib.sha256(secret.encode("utf-8")).digest()

    @classmethod
    def _get_fernet_cipher(cls) -> Fernet:
        """Derives a legacy Fernet cipher for backwards-compatible token decryption."""
        key = base64.urlsafe_b64encode(cls._get_aes_key())
        return Fernet(key)

    @classmethod
    def encrypt_join_code(cls, code: str) -> str:
        """Encrypts join code using authenticated AES-256-GCM encryption with 96-bit nonce."""
        clean = code.strip().upper()
        key = cls._get_aes_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # 96-bit CSPRNG IV
        ciphertext = aesgcm.encrypt(nonce, clean.encode("utf-8"), None)
        nonce_b64 = base64.b64encode(nonce).decode("ascii")
        ct_b64 = base64.b64encode(ciphertext).decode("ascii")
        return f"enc_v1:{nonce_b64}:{ct_b64}"

    @classmethod
    def decrypt_join_code(cls, token: str | None) -> str | None:
        """Decrypts join code token. Supports AES-256-GCM and legacy Fernet tokens."""
        if not token:
            return None
        token_clean = token.strip()

        # 1. Primary: AES-256-GCM format 'enc_v1:{nonce}:{ciphertext}'
        if token_clean.startswith("enc_v1:"):
            try:
                parts = token_clean.split(":")
                if len(parts) == 3:
                    nonce = base64.b64decode(parts[1])
                    ciphertext = base64.b64decode(parts[2])
                    key = cls._get_aes_key()
                    aesgcm = AESGCM(key)
                    decrypted = aesgcm.decrypt(nonce, ciphertext, None)
                    return decrypted.decode("utf-8")
            except Exception as e:
                logger.warning("AES-256-GCM join code decryption failed", error=str(e))
                return None

        # 2. Fallback: Legacy Fernet token
        try:
            cipher = cls._get_fernet_cipher()
            return cipher.decrypt(token_clean.encode("utf-8")).decode("utf-8")
        except Exception:
            return None

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

        member_role = (member.role or "").strip().upper()
        if member_role not in ["OWNER", "ADMIN"]:
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

    # ── Creator-Scoped Settings Retrieval (Decision Q1) ───────────────────────

    async def get_join_code_settings(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        is_platform_admin: bool = False,
    ) -> JoinCodeSettingsSchema:
        """Fetches safe creator-scoped join code configuration. Plaintext and hash are NEVER returned."""
        await self._verify_actor_authority(workspace_id, user_id, is_platform_admin)

        # 1. Query dedicated creator-scoped table
        code_record = await self.join_code_repo.get_any_active_by_user(session, workspace_id, user_id)
        if code_record:
            return JoinCodeSettingsSchema(
                enabled=code_record.is_enabled,
                default_role="MEMBER",
                require_approval=False,
                expires_at=code_record.expires_at,
                generated_at=code_record.created_at,
                generated_by=code_record.created_by_user_id or code_record.operational_custodian_user_id,
                has_code=bool(code_record.code_hash),
                max_uses=None,
                current_uses=code_record.use_count,
            )

        # 2. Fallback to settings_json for unmigrated legacy workspaces
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

    # ── Creator-Scoped Settings Mutation (Decision Q1) ────────────────────────

    async def patch_join_code_settings(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        request: JoinCodeSettingsPatchRequest,
        is_platform_admin: bool = False,
    ) -> JoinCodeSettingsSchema:
        """Patches creator-scoped join code administrative settings."""
        await self._verify_actor_authority(workspace_id, user_id, is_platform_admin)

        if request.default_role is not None and request.default_role not in self.ALLOWED_ROLES:
            raise ValueError(f"Default role must be 'MEMBER', got '{request.default_role}'.")

        # 1. Update dedicated creator-scoped record if present
        code_record = await self.join_code_repo.get_any_active_by_user(session, workspace_id, user_id)
        if code_record:
            if request.enabled is not None:
                code_record.is_enabled = request.enabled
            if request.expires_in_days is not None:
                if request.expires_in_days == 0:
                    code_record.expires_at = datetime.now(UTC) + timedelta(days=3650)
                else:
                    code_record.expires_at = datetime.now(UTC) + timedelta(days=request.expires_in_days)
            code_record.version += 1
            code_record.updated_at = datetime.now(UTC)
            session.add(code_record)

        # 2. Maintain settings_json for backward compatibility
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
        if request.expires_in_days is not None:
            if request.expires_in_days == 0:
                join_code_config["expires_at"] = None
            else:
                now = datetime.now(UTC)
                join_code_config["expires_at"] = (now + timedelta(days=request.expires_in_days)).isoformat()

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
            resource_id=str(code_record.id if code_record else workspace_id),
            details={
                "enabled": request.enabled,
                "expires_in_days": request.expires_in_days,
            },
            status="success",
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()
        await self._invalidate_settings_cache(workspace_id)

        return await self.get_join_code_settings(session, workspace_id, user_id, is_platform_admin)

    # ── Independent Generation & Regeneration (Decision Q1) ───────────────────

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
        """Generates or regenerates an independent creator-scoped Join Code.

        In strict accordance with Decision Q1 (Option A):
        - Creates or rotates the code for created_by_user_id = user_id.
        - Deactivates previous active code owned by this creator ONLY.
        - Other creators' codes in the workspace remain completely untouched!
        - Plaintext code is returned strictly once upon generation.
        """
        await self._verify_actor_authority(workspace_id, user_id, is_platform_admin)

        role_clean = default_role.strip().upper()
        if role_clean not in self.ALLOWED_ROLES:
            raise ValueError(f"Default role must be 'MEMBER', got '{default_role}'.")

        # 1. Cryptographically generate plaintext code, candidate lookup hash, and encrypted storage
        plaintext_code = self.generate_plaintext_code()
        code_hash_v2 = self.compute_candidate_hash(plaintext_code, pepper_version="v2", workspace_id=workspace_id)
        encrypted_code = self.encrypt_join_code(plaintext_code)
        legacy_bcrypt_hash = self.hash_join_code(plaintext_code)

        # 2. Compute expiration
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=expires_in_days) if expires_in_days > 0 else (now + timedelta(days=3650))

        # 3. Disable previous active code for THIS creator only (Q1 isolation guarantee)
        await self.join_code_repo.disable_active_for_creator(session, workspace_id, user_id)

        # 4. Insert into dedicated workspace_join_codes table
        display_tail = plaintext_code.split("-")[-1] if "-" in plaintext_code else plaintext_code[-4:]
        code_record = WorkspaceJoinCode(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            created_by_user_id=user_id,
            operational_custodian_user_id=None,
            code_hash=code_hash_v2,
            lookup_pepper_version="v2",
            encrypted_code=encrypted_code,
            encryption_key_version="enc_v1",
            code_display=f"VR-{display_tail[:2]}****",
            is_enabled=True,
            is_legacy=False,
            expires_at=expires_at,
            use_count=0,
            version=1,
        )
        await self.join_code_repo.create(session, code_record)

        # 5. Mirror to settings_json for backward compatibility with unmigrated paths
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

        new_join_config = {
            "is_enabled": True,
            "code_hash": legacy_bcrypt_hash,
            "code_encrypted": encrypted_code,
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

        # 6. Snapshot to history table
        history_entry = WorkspaceSettingsHistory(
            workspace_id=workspace_id,
            schema_version=settings.schema_version or 1,
            version=settings.version,
            settings_json=settings_dict,
            settings_hash=settings.settings_hash,
            changed_by_user_id=user_id,
            change_reason="JOIN_CODE_REGENERATED" if is_regeneration else "JOIN_CODE_GENERATED",
        )
        session.add(history_entry)

        # 7. Audit log entry with non-secret metadata
        audit_log = AuditLog(
            tenant_id=workspace_id,
            action="JOIN_CODE_REGENERATED" if is_regeneration else "JOIN_CODE_GENERATED",
            user_id=user_id,
            resource_type="WORKSPACE_JOIN_CODE",
            resource_id=str(code_record.id),
            details={
                "expires_at": expires_at.isoformat(),
                "default_role": "MEMBER",
                "has_code": True,
                "created_by": str(user_id),
            },
            status="success",
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()
        await self._invalidate_settings_cache(workspace_id)

        # 8. Reveal plaintext strictly once
        return JoinCodeGenerateResponse(
            success=True,
            join_code=plaintext_code,
            expires_at=expires_at,
            default_role="MEMBER",
            warning=(
                "This Join Code will only be displayed once. Copy and share it with your team now. "
                "Veritas-RAG stores only a cryptographic hash and cannot retrieve this code later."
            ),
        )

    # ── Candidate Validation Service (Decisions Q1 & Q3) ──────────────────────

    async def validate_join_code_candidate(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        candidate_code: str,
        return_record: bool = False,
    ) -> tuple:
        """Validates candidate join code against active codes in the workspace.

        Supports:
        1. Primary: Dual-pepper candidate lookup in workspace_join_codes (v2 primary, v1 fallback).
        2. Fallback: Legacy settings_json inspection for unmigrated workspaces.
        3. Unlimited redemption (Decision Q3): use_count does NOT block joining.
        4. Metadata exposure (V1.7): returns code_record when return_record=True.
        """
        def _res(valid: bool, reason: str | None, role: str, rec: WorkspaceJoinCode | None = None) -> tuple:
            return (valid, reason, role, rec) if return_record else (valid, reason, role)

        if not candidate_code or not isinstance(candidate_code, str):
            return _res(False, "Invalid join code format.", "")

        clean = candidate_code.strip().upper()
        if not re.match(JOIN_CODE_PATTERN, clean):
            return _res(False, "Invalid join code format. Expected 'VR-XXXXXX'.", "")

        now = datetime.now(UTC)

        # 1. Primary path: Dual-pepper candidate lookup in workspace_join_codes
        try:
            # Check with primary pepper v2
            hash_v2 = self.compute_candidate_hash(clean, pepper_version="v2", workspace_id=workspace_id)
            code_record = await self.join_code_repo.find_candidate_by_hash(session, workspace_id, hash_v2)

            # If not found with v2, check with fallback pepper v1
            if not code_record:
                hash_v1 = self.compute_candidate_hash(clean, pepper_version="v1", workspace_id=workspace_id)
                code_record = await self.join_code_repo.find_candidate_by_hash(session, workspace_id, hash_v1)
                # Transparent upgrade from v1 to v2 on successful validation
                if code_record and code_record.lookup_pepper_version == "v1":
                    code_record.code_hash = hash_v2
                    code_record.lookup_pepper_version = "v2"
                    code_record.updated_at = now
                    code_record.version += 1
                    session.add(code_record)
                    await session.flush()
                    await session.commit()
                    logger.info(
                        "Transparently upgraded join code from pepper v1 to v2",
                        code_id=str(code_record.id),
                    )

            if code_record:
                if not code_record.is_enabled:
                    return _res(False, "Join Code entry is currently disabled for this workspace.", "", code_record)

                # Check expiration
                expires_at = code_record.expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                if now >= expires_at:
                    return _res(False, "Join code has expired.", "", code_record)

                # Decision Q3: Unlimited redemption - use_count does NOT block joining
                return _res(True, None, "MEMBER", code_record)
        except Exception as ex:
            logger.warning("Error querying workspace_join_codes table; falling back to settings", error=str(ex))

        # 2. Fallback path: Legacy workspace_settings inspection
        settings = await self.settings_repo.get_by_workspace_id(workspace_id)
        if not settings or not settings.settings_json:
            return _res(False, "Workspace settings not found.", "")

        config = settings.settings_json.get("join_code", {})
        if not config.get("is_enabled", False):
            return _res(False, "Join Code entry is currently disabled for this workspace.", "")

        stored_hash = config.get("code_hash")
        if not stored_hash:
            return _res(False, "No active join code configured.", "")

        # Check expiration
        expires_at_str = config.get("expires_at")
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                if now >= expires_at:
                    return _res(False, "Join code has expired.", "")
            except (ValueError, TypeError):
                return _res(False, "Invalid expiration format in stored configuration.", "")

        # Check usage limits for legacy unmigrated codes
        max_uses = config.get("max_uses")
        current_uses = config.get("current_uses", 0)
        if max_uses is not None and current_uses >= max_uses:
            return _res(False, "Join code usage limit has been reached.", "")

        # Constant-time cryptographic verification
        if not self.verify_join_code(clean, stored_hash):
            return _res(False, "Invalid join code.", "")

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
            except Exception as e:
                logger.warning("Failed to transparently upgrade legacy join code hash", error=str(e))

        default_role = config.get("default_role", "MEMBER")
        return _res(True, None, default_role)

    async def validate_join_code_candidate_full(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        candidate_code: str,
    ) -> tuple[bool, str | None, str, WorkspaceJoinCode | None]:
        """Convenience method returning candidate validation results along with the resolved code record."""
        return await self.validate_join_code_candidate(
            session=session,
            workspace_id=workspace_id,
            candidate_code=candidate_code,
            return_record=True,
        )

    async def record_join_code_usage(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        code_id: uuid.UUID | None = None,
    ) -> None:
        """Increments usage count when a join code is successfully consumed.

        Decision Question 5 Approved:
        When code_id is provided, increments usage count on that exact code entity.
        If code_id is None, falls back to incrementing the first active code found.
        Maintains settings_json usage count for legacy compatibility.
        """
        # 1. Increment on specific code if provided, or active creator-scoped code
        try:
            if code_id:
                await self.join_code_repo.increment_usage(session, code_id)
            else:
                now = datetime.now(UTC)
                codes = await self.join_code_repo.list_by_workspace(session, workspace_id)
                for c in codes:
                    if c.is_enabled and c.expires_at > now:
                        await self.join_code_repo.increment_usage(session, c.id)
                        break
        except Exception as ex:
            logger.warning("Could not increment usage in workspace_join_codes", error=str(ex))

        # 2. Maintain settings_json usage count for legacy compatibility
        settings = await self.settings_repo.get_by_workspace_id_for_update(workspace_id)
        if settings and settings.settings_json:
            settings_dict = dict(settings.settings_json)
            jc = dict(settings_dict.get("join_code", {}))
            current = jc.get("current_uses", 0)
            jc["current_uses"] = current + 1
            settings_dict["join_code"] = jc
            settings.settings_json = settings_dict
            settings.version += 1
            settings.settings_hash = _compute_settings_hash(settings_dict)
            session.add(settings)
            await session.flush()
            await self._invalidate_settings_cache(workspace_id)
            logger.info(
                "Incremented workspace join code usage count",
                workspace_id=str(workspace_id),
                current_uses=jc["current_uses"],
            )

    # ── Join Code Access Routing (Protected File #1 Target) ────────────────────

    async def get_join_access(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        is_platform_admin: bool = False,
    ) -> WorkspaceJoinAccessResponse:
        """Retrieves active Join Code and canonical Join Link for an authenticated member.

        Preserves Protected File #1 (workspaces.py) at 0-bit drift.
        Enforces tenant isolation, membership validation, and creator-scoped retrieval.
        """
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace or workspace.status != WorkspaceStatus.ACTIVE.value:
            raise WorkspaceNotFoundError("Workspace not found or inactive.")

        if not is_platform_admin:
            member = await self.member_repo.get_membership(workspace_id, user_id)
            if not member or member.status != MemberStatus.ACTIVE.value or member.is_deleted:
                raise WorkspaceUnauthorizedError("Access denied. Active workspace membership required.")

        now = datetime.now(UTC)

        # 1. Primary: check for creator's own active code (or custodied code)
        code_record = await self.join_code_repo.get_any_active_by_user(session, workspace_id, user_id)
        if code_record and code_record.is_enabled and code_record.expires_at > now:
            decrypted_code = self.decrypt_join_code(code_record.encrypted_code)
            if decrypted_code:
                identifier = workspace.public_id or workspace.slug or str(workspace_id)
                clean_id = identifier.strip()
                clean_code = decrypted_code.strip().upper()
                join_link = f"/workspaces/join?workspace_id={clean_id}&join_code={clean_code}"
                return WorkspaceJoinAccessResponse(
                    success=True,
                    workspace_id=workspace_id,
                    public_id=workspace.public_id,
                    workspace_name=workspace.name,
                    has_active_code=True,
                    join_code=decrypted_code,
                    join_link=join_link,
                    expires_at=code_record.expires_at,
                    default_role="MEMBER",
                )

        # 2. Fallback: check workspace_settings
        settings = await self.settings_repo.get_by_workspace_id(workspace_id)
        config: dict[str, Any] = {}
        if settings and settings.settings_json:
            config = settings.settings_json.get("join_code", {})

        is_enabled = bool(config.get("is_enabled", False))
        code_hash = config.get("code_hash")
        code_encrypted = config.get("code_encrypted")
        expires_at_val = config.get("expires_at")
        default_role = config.get("default_role", "MEMBER")

        expires_at = datetime.fromisoformat(expires_at_val) if expires_at_val else None
        is_expired = False
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if now >= expires_at:
                is_expired = True

        has_active_code = is_enabled and bool(code_hash) and not is_expired
        decrypted_code: str | None = None
        join_link: str | None = None

        if has_active_code and code_encrypted:
            decrypted_code = self.decrypt_join_code(code_encrypted)
            if decrypted_code:
                identifier = workspace.public_id or workspace.slug or str(workspace_id)
                clean_id = identifier.strip()
                clean_code = decrypted_code.strip().upper()
                join_link = f"/workspaces/join?workspace_id={clean_id}&join_code={clean_code}"

        return WorkspaceJoinAccessResponse(
            success=True,
            workspace_id=workspace_id,
            public_id=workspace.public_id,
            workspace_name=workspace.name,
            has_active_code=has_active_code and bool(decrypted_code),
            join_code=decrypted_code if has_active_code else None,
            join_link=join_link if has_active_code else None,
            expires_at=expires_at,
            default_role=default_role,
        )

    # ── Dynamic Member Join Access Resolution (V1.7 Specification) ───────────

    async def resolve_member_join_credentials(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        caller_id: uuid.UUID,
    ) -> MemberJoinAccessResponse:
        """Resolves join credentials for an existing workspace member dynamically."""
        # 1. Fetch caller membership
        caller_member = await self.member_repo.get_membership(workspace_id, caller_id)
        if not caller_member or caller_member.status != MemberStatus.ACTIVE.value or caller_member.is_deleted:
            raise WorkspaceUnauthorizedError("Active workspace membership required.")

        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError("Target workspace not found.")
        ws_name = workspace.name or "Workspace"
        pub_id = workspace.public_id or workspace.slug

        caller_role = caller_member.role.upper() if caller_member.role else ""

        # 2. Strict Single-Reveal Guard: Prevent OWNER / ADMIN plaintext recovery loop
        if caller_role in ("OWNER", "ADMIN"):
            own_code = await self.join_code_repo.get_any_active_by_user(session, workspace_id, caller_id)
            return MemberJoinAccessResponse(
                success=True,
                status=MemberAccessStatusEnum.ADMIN_MANAGEMENT_REQUIRED,
                workspace_id=workspace_id,
                workspace_name=ws_name,
                public_id=pub_id,
                creator_name=None,
                join_code=None,
                join_link=None,
                code_display=own_code.code_display if own_code else None,
                expires_at=own_code.expires_at if own_code else None,
                message="Administrators manage join codes in Workspace Settings. Plaintext recovery is disabled under single-reveal policy.",
            )

        # 3. Decision P6 Policy Gate for VIEWER
        if caller_role == "VIEWER":
            raise WorkspaceUnauthorizedError("Viewers are not authorized to distribute workspace join credentials.")

        # 4. Explicit Role Allowlist: Only MEMBER proceeds to peer-sharing resolution
        if caller_role != "MEMBER":
            raise WorkspaceUnauthorizedError(f"Role '{caller_role}' is not authorized to access join credentials.")

        # 5. Read Originating Creator Attribution & Check for Conflicts
        relational_creator_id = caller_member.invited_by_user_id
        meta = caller_member.member_metadata or {}
        snapshot = meta.get("attribution_snapshot", {}) if isinstance(meta, dict) else {}
        snapshot_creator_str = snapshot.get("creator_user_id")
        snapshot_creator_id = uuid.UUID(snapshot_creator_str) if snapshot_creator_str else None

        # Attribution Conflict Detection
        if relational_creator_id and snapshot_creator_id and relational_creator_id != snapshot_creator_id:
            logger.error(
                "security.attribution.snapshot_conflict_detected",
                workspace_id=str(workspace_id),
                member_id=str(caller_member.id),
                user_id=str(caller_id),
                relational_creator_id=str(relational_creator_id),
                snapshot_creator_id=str(snapshot_creator_id),
            )
            return MemberJoinAccessResponse(
                success=True,
                status=MemberAccessStatusEnum.ATTRIBUTION_CONFLICT,
                workspace_id=workspace_id,
                workspace_name=ws_name,
                public_id=pub_id,
                creator_name=None,
                join_code=None,
                join_link=None,
                code_display=None,
                expires_at=None,
                message="Attribution integrity conflict detected on your membership. Credential sharing is temporarily suspended. Please contact your workspace administrator.",
            )

        # Resolve authoritative creator target
        creator_id = relational_creator_id or snapshot_creator_id
        if not creator_id:
            return MemberJoinAccessResponse(
                success=True,
                status=MemberAccessStatusEnum.NO_ATTRIBUTION,
                workspace_id=workspace_id,
                workspace_name=ws_name,
                public_id=pub_id,
                creator_name=None,
                join_code=None,
                join_link=None,
                code_display=None,
                expires_at=None,
                message="No originating administrator attribution is recorded for your membership. Please contact your workspace administrator.",
            )

        # 6. Complete Dashboard Creator Eligibility Validation
        creator_user = await session.get(User, creator_id)
        if not creator_user or not creator_user.is_active or creator_user.is_deleted:
            c_name = getattr(creator_user, "display_name", None) or "Administrator"
            return MemberJoinAccessResponse(
                success=True,
                status=MemberAccessStatusEnum.CREATOR_INELIGIBLE,
                workspace_id=workspace_id,
                workspace_name=ws_name,
                public_id=pub_id,
                creator_name=c_name,
                join_code=None,
                join_link=None,
                code_display=None,
                expires_at=None,
                message=f"Your originating administrator ({c_name}) is no longer active. Please contact the workspace owner.",
            )

        creator_member = await self.member_repo.get_membership(workspace_id, creator_id)
        c_name = getattr(creator_user, "display_name", None) or getattr(creator_user, "full_name", None) or "Administrator"

        if (
            not creator_member
            or creator_member.status != MemberStatus.ACTIVE.value
            or creator_member.is_deleted
            or (creator_member.role and creator_member.role.upper() not in ("OWNER", "ADMIN"))
        ):
            return MemberJoinAccessResponse(
                success=True,
                status=MemberAccessStatusEnum.CREATOR_INELIGIBLE,
                workspace_id=workspace_id,
                workspace_name=ws_name,
                public_id=pub_id,
                creator_name=c_name,
                join_code=None,
                join_link=None,
                code_display=None,
                expires_at=None,
                message=f"Your originating administrator ({c_name}) is no longer eligible to manage workspace join credentials. Please contact the workspace owner.",
            )

        # 7. Query creator's current join code
        code_record = await self.join_code_repo.get_any_active_by_user(session, workspace_id, creator_id)
        if not code_record:
            latest_code = await self.join_code_repo.get_latest_by_creator(session, workspace_id, creator_id)
            if latest_code:
                now_utc = datetime.now(UTC)
                exp = latest_code.expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=UTC)
                # Composite state check: Revoked/disabled takes precedence over natural expiration
                if not latest_code.is_enabled:
                    return MemberJoinAccessResponse(
                        success=True,
                        status=MemberAccessStatusEnum.REVOKED,
                        workspace_id=workspace_id,
                        workspace_name=ws_name,
                        public_id=pub_id,
                        creator_name=c_name,
                        join_code=None,
                        join_link=None,
                        code_display=None,
                        expires_at=exp,
                        message=f"The join code created by {c_name} has been deactivated. Please contact {c_name} for an updated code.",
                    )
                if exp <= now_utc:
                    return MemberJoinAccessResponse(
                        success=True,
                        status=MemberAccessStatusEnum.EXPIRED,
                        workspace_id=workspace_id,
                        workspace_name=ws_name,
                        public_id=pub_id,
                        creator_name=c_name,
                        join_code=None,
                        join_link=None,
                        code_display=None,
                        expires_at=exp,
                        message=f"The join code created by {c_name} expired on {exp.strftime('%Y-%m-%d')}. Please contact {c_name} to regenerate it.",
                    )
            return MemberJoinAccessResponse(
                success=True,
                status=MemberAccessStatusEnum.NO_CODE_CONFIGURED,
                workspace_id=workspace_id,
                workspace_name=ws_name,
                public_id=pub_id,
                creator_name=c_name,
                join_code=None,
                join_link=None,
                code_display=None,
                expires_at=None,
                message=f"Your originating administrator ({c_name}) does not currently have an active join code configured.",
            )

        # 8. Active Code Found: Decrypt and return canonical link for Member peer sharing
        plaintext = self.decrypt_join_code(code_record.encrypted_code)
        identifier = pub_id or str(workspace_id)
        clean_id = identifier.strip()
        clean_code = plaintext.strip().upper() if plaintext else ""
        canonical_link = f"/workspaces/join?workspace_id={clean_id}&join_code={clean_code}"

        return MemberJoinAccessResponse(
            success=True,
            status=MemberAccessStatusEnum.ACTIVE,
            workspace_id=workspace_id,
            workspace_name=ws_name,
            public_id=pub_id,
            creator_name=c_name,
            join_code=plaintext,
            join_link=canonical_link,
            code_display=None,
            expires_at=code_record.expires_at,
            message="Current active join credentials.",
        )

    # ── Operational Custodian Protocol (Correction C5) ────────────────────────

    async def claim_legacy_join_code(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        claiming_owner_id: uuid.UUID,
        code_id: uuid.UUID,
    ) -> WorkspaceJoinCode:
        """Allows an active workspace OWNER to claim operational custodianship of an unmapped legacy code.

        In strict accordance with Correction C5:
        - Sets operational_custodian_user_id = claiming_owner_id.
        - Sets is_enabled = TRUE (un-quarantines the code).
        - created_by_user_id remains strictly NULL to preserve historical provenance.
        - Verified custodian acquires full operational rights.
        """
        # 1. Enforce actor is OWNER
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace or workspace.status != WorkspaceStatus.ACTIVE.value:
            raise WorkspaceNotFoundError("Workspace not found or inactive.")

        member = await self.member_repo.get_membership(workspace_id, claiming_owner_id)
        if not member or member.role.upper() != "OWNER":
            raise WorkspaceUnauthorizedError("Only an active workspace OWNER can claim operational custodianship.")

        # 2. Retrieve code
        code_record = await self.join_code_repo.get_by_id(session, code_id, workspace_id)
        if not code_record:
            raise WorkspaceNotFoundError("Join code not found.")

        if not code_record.is_legacy or code_record.created_by_user_id is not None:
            raise WorkspaceUnauthorizedError("Only unmapped legacy codes can be claimed by an operational custodian.")

        # 3. Update custodian while keeping creator provenance immutable
        code_record.operational_custodian_user_id = claiming_owner_id
        code_record.is_enabled = True
        code_record.version += 1
        code_record.updated_at = datetime.now(UTC)
        session.add(code_record)

        audit_log = AuditLog(
            tenant_id=workspace_id,
            action="workspace.join_code.custodian_claimed",
            user_id=claiming_owner_id,
            resource_type="WORKSPACE_JOIN_CODE",
            resource_id=str(code_record.id),
            details={
                "previous_custodian": None,
                "new_custodian": str(claiming_owner_id),
                "is_legacy": True,
            },
            status="success",
        )
        session.add(audit_log)

        await session.flush()
        await session.commit()
        await self._invalidate_settings_cache(workspace_id)
        return code_record

    # ── Coordinated HMAC Pepper Retirement Protocol (Correction C7) ───────────

    async def migrate_retained_records_to_v2(self, session: AsyncSession) -> int:
        """Migrates ALL retained records (both enabled and disabled) from pepper v1 to v2.

        In strict accordance with Correction C7 Stage 2:
        - Decrypts code using AES-256-GCM.
        - Computes code_hash with pepper v2.
        - Updates code_hash and lookup_pepper_version = 'v2'.
        """
        from sqlalchemy import select
        stmt = select(WorkspaceJoinCode).where(
            WorkspaceJoinCode.lookup_pepper_version == "v1",
            WorkspaceJoinCode.is_deleted.is_(False),
        )
        res = await session.execute(stmt)
        records = res.scalars().all()
        migrated_count = 0

        for r in records:
            plaintext = self.decrypt_join_code(r.encrypted_code)
            if plaintext:
                r.code_hash = self.compute_candidate_hash(plaintext, pepper_version="v2", workspace_id=r.workspace_id)
                r.lookup_pepper_version = "v2"
                r.updated_at = datetime.now(UTC)
                r.version += 1
                session.add(r)
                migrated_count += 1

        await session.flush()
        await session.commit()
        return migrated_count

    async def verify_zero_v1_references(self, session: AsyncSession) -> bool:
        """Verifies that no record in workspace_join_codes references retiring pepper v1 (C7 Stage 3)."""
        count = await self.join_code_repo.count_by_pepper_version(session, "v1")
        return count == 0

    # ── Creator-Scoped Extended Operations (Master Plan WP-4) ─────────────────

    async def get_creator_join_code(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        is_platform_admin: bool = False,
    ) -> tuple[WorkspaceJoinCode | None, str | None]:
        """Retrieves the active join code owned or managed by this creator, along with decrypted plaintext."""
        await self._verify_actor_authority(workspace_id, user_id, is_platform_admin)
        code = await self.join_code_repo.get_any_active_by_user(session, workspace_id, user_id)
        if not code:
            return None, None
        plaintext = self.decrypt_join_code(code.encrypted_code)
        return code, plaintext

    async def revoke_creator_join_code(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        code_id: uuid.UUID,
        actor_id: uuid.UUID,
        is_platform_admin: bool = False,
    ) -> WorkspaceJoinCode:
        """Revokes an active join code. Only the creator or operational custodian may revoke their code."""
        await self._verify_actor_authority(workspace_id, actor_id, is_platform_admin)
        code = await self.join_code_repo.get_by_id(session, code_id, workspace_id)
        if not code:
            raise WorkspaceNotFoundError("Join code not found in this workspace.")

        is_creator = code.created_by_user_id == actor_id
        is_custodian = code.operational_custodian_user_id == actor_id
        if not (is_creator or is_custodian or is_platform_admin):
            raise WorkspaceUnauthorizedError("Only the creator or operational custodian can revoke this join code.")

        code.is_enabled = False
        code.version += 1
        code.updated_at = datetime.now(UTC)
        session.add(code)

        audit_log = AuditLog(
            tenant_id=workspace_id,
            action="workspace.join_code.revoked",
            user_id=actor_id,
            resource_type="WORKSPACE_JOIN_CODE",
            resource_id=str(code.id),
            details={"is_creator": is_creator, "is_custodian": is_custodian},
            status="success",
        )
        session.add(audit_log)
        await session.flush()
        return code

    async def list_creator_redemptions(
        self,
        session: AsyncSession,
        workspace_id: uuid.UUID,
        creator_user_id: uuid.UUID,
        is_platform_admin: bool = False,
    ) -> Sequence[WorkspaceJoinCodeRedemption]:
        """Lists redemptions for codes created or managed by the requesting creator."""
        await self._verify_actor_authority(workspace_id, creator_user_id, is_platform_admin)
        return await self.join_code_repo.list_redemptions(
            session=session,
            workspace_id=workspace_id,
            creator_user_id=creator_user_id,
        )

