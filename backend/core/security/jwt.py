"""Native JWT Issuance and Verification.

Supports RS256 token generation and validation.
Incorporates Redis token blocklist logic.
"""

import os
import time
from typing import Any
import uuid

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
import structlog

from backend.cache.client import get_redis_client
from backend.core.auth.context import TokenPayload
from backend.core.exceptions.auth import ExpiredTokenException, InvalidTokenException

logger = structlog.get_logger(__name__)

# Default fallback secret for development environments
_DEV_FALLBACK_SECRET = "fallback-secret-key-do-not-use-in-production"


class JWTService:
    """Handles native JWT generation, validation, and Redis blocklisting."""

    def __init__(
        self,
        signing_algorithm: str | None = None,
        allowed_algorithms: list[str] | None = None,
        hmac_secret_key: str | None = None,
        rsa_private_key: str | None = None,
        rsa_public_key: str | None = None,
    ) -> None:
        try:
            from backend.core.config import get_settings
            settings = get_settings()
            sec = settings.security
        except Exception:
            sec = None

        self.signing_algorithm = (
            signing_algorithm
            or (getattr(sec, "jwt_signing_algorithm", None) if sec else None)
            or os.getenv("JWT_SIGNING_ALGORITHM")
            or "HS256"
        )
        self.allowed_algorithms = (
            allowed_algorithms
            or (getattr(sec, "allowed_jwt_algorithms", None) if sec else None)
            or ["HS256"]
        )

        self.hmac_secret_key = (
            hmac_secret_key
            or (getattr(sec, "jwt_secret_key", None) if sec else None)
            or os.getenv("JWT_SECRET_KEY")
            or os.getenv("APP_SECRET_KEY")
            or _DEV_FALLBACK_SECRET
        )
        self.rsa_private_key = (
            rsa_private_key
            or (getattr(sec, "jwt_private_key", None) if sec else None)
            or os.getenv("JWT_PRIVATE_KEY")
        )
        self.rsa_public_key = (
            rsa_public_key
            or (getattr(sec, "jwt_public_key", None) if sec else None)
            or os.getenv("JWT_PUBLIC_KEY")
        )

        if self.signing_algorithm == "RS256":
            self.private_key = self.rsa_private_key
            self.public_key = self.rsa_public_key
            self.algorithm = "RS256"
        else:
            self.private_key = self.hmac_secret_key
            self.public_key = self.hmac_secret_key
            self.algorithm = "HS256"

        self.redis = get_redis_client()
        self.issuer = "raguard-auth-server"
        self.audience = "raguard-api"

    async def issue_tokens(
        self,
        user: Any,
        session: Any | None = None,
        workspace_id: str | uuid.UUID | None = None,
        role: str | None = None,
        family_id: str | None = None,
        demo_simulated: bool = False,
    ) -> tuple[str, str, str]:
        """Issue access and refresh tokens.

        Derives active workspace context and authoritative role from:
        1. Explicitly provided workspace_id and role.
        2. Saved active workspace on user (user.tenant_id) if active membership exists.
        3. First active workspace membership.
        4. None if user belongs to no active workspaces.

        Returns:
            Tuple containing:
            - access_token (str)
            - raw_refresh_token (str)
            - family_id (str)
        """
        now = int(time.time())
        access_exp = now + (15 * 60) # 15 minutes

        access_jti = str(uuid.uuid4())

        resolved_workspace_id = str(workspace_id) if workspace_id else None
        resolved_role = role

        if resolved_role == "platform_admin":
            resolved_workspace_id = None

        if session and not (resolved_role and (resolved_workspace_id or resolved_role == "platform_admin")):
            from sqlalchemy import select
            from backend.models.entities.workspace import Workspace, WorkspaceStatus
            from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember

            # 1. If explicit workspace_id was passed, resolve role from membership if needed
            if resolved_workspace_id:
                try:
                    target_ws_uuid = uuid.UUID(resolved_workspace_id)
                except (ValueError, TypeError):
                    target_ws_uuid = None

                if target_ws_uuid and not resolved_role:
                    stmt = (
                        select(WorkspaceMember.role)
                        .where(
                            WorkspaceMember.workspace_id == target_ws_uuid,
                            WorkspaceMember.user_id == user.id,
                            WorkspaceMember.status == MemberStatus.ACTIVE.value,
                            WorkspaceMember.is_deleted == False,
                        )
                        .limit(1)
                    )
                    res = await session.execute(stmt)
                    member_role = res.scalar_one_or_none()
                    if member_role:
                        resolved_role = member_role

            # 2. If workspace_id was not passed, check user's saved active workspace context (user.tenant_id)
            elif getattr(user, "tenant_id", None) and resolved_role != "platform_admin":
                try:
                    saved_ws_uuid = uuid.UUID(str(user.tenant_id))
                except (ValueError, TypeError):
                    saved_ws_uuid = None

                if saved_ws_uuid:
                    stmt = (
                        select(Workspace.id, WorkspaceMember.role)
                        .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
                        .where(
                            Workspace.id == saved_ws_uuid,
                            WorkspaceMember.user_id == user.id,
                            Workspace.status == WorkspaceStatus.ACTIVE.value,
                            WorkspaceMember.status == MemberStatus.ACTIVE.value,
                            WorkspaceMember.is_deleted == False,
                        )
                        .limit(1)
                    )
                    res = await session.execute(stmt)
                    row = res.first()
                    if row:
                        resolved_workspace_id = str(row[0])
                        if not resolved_role:
                            resolved_role = row[1]

            # 3. If still not resolved, query user's first active workspace and its role
            if not resolved_workspace_id and resolved_role != "platform_admin":
                stmt = (
                    select(Workspace.id, WorkspaceMember.role)
                    .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
                    .where(
                        WorkspaceMember.user_id == user.id,
                        Workspace.status == WorkspaceStatus.ACTIVE.value,
                        WorkspaceMember.status == MemberStatus.ACTIVE.value,
                        WorkspaceMember.is_deleted == False,
                    )
                    .order_by(Workspace.created_at.asc())
                    .limit(1)
                )
                res = await session.execute(stmt)
                row = res.first()
                if row:
                    resolved_workspace_id = str(row[0])
                    if not resolved_role:
                        resolved_role = row[1]

        if not resolved_role:
            resolved_role = getattr(user, "role", "viewer")

        resolved_family_id = family_id or str(uuid.uuid4())

        access_claims = {
            "sub": str(user.id),
            "iss": self.issuer,
            "aud": self.audience,
            "exp": access_exp,
            "iat": now,
            "nbf": now,
            "jti": access_jti,
            "role": resolved_role,
            "email": getattr(user, "email", None),
            "workspace_id": resolved_workspace_id,
            "family_id": resolved_family_id,
            "demo_simulated": demo_simulated,
        }

        access_token = jwt.encode(access_claims, self.private_key, algorithm=self.algorithm)

        import secrets
        raw_refresh_token = secrets.token_urlsafe(64)

        return access_token, raw_refresh_token, resolved_family_id

    async def verify_token(self, token: str) -> TokenPayload:
        """Decode and verify an Access token, checking the Redis blocklist."""
        try:
            try:
                header = jwt.get_unverified_header(token)
            except Exception as e:
                raise InvalidTokenException(f"Malformed token header: {e}") from e

            token_alg = header.get("alg")
            if not token_alg or token_alg not in self.allowed_algorithms or token_alg.lower() == "none":
                raise InvalidTokenException(f"Unauthorized token algorithm: {token_alg}")

            if token_alg == "RS256":
                if not self.rsa_public_key:
                    raise InvalidTokenException("RS256 public key not configured")
                verification_key = self.rsa_public_key
            elif token_alg == "HS256":
                if not self.hmac_secret_key:
                    raise InvalidTokenException("HS256 secret key not configured")
                verification_key = self.hmac_secret_key
            else:
                raise InvalidTokenException(f"Algorithm key mapping undefined for: {token_alg}")

            raw_claims = jwt.decode(
                token,
                verification_key,
                algorithms=[token_alg],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iss", "aud", "sub", "jti", "nbf"]},
            )

            jti = raw_claims.get("jti")
            sub = str(raw_claims.get("sub"))
            workspace_id = raw_claims.get("workspace_id")

            if not jti:
                raise InvalidTokenException("Token lacks required 'jti' claim")

            # Check Redis Blocklist (F2.4)
            if self.redis:
                is_blocked = await self.redis.get(f"auth:blocklist:{jti}")
                if is_blocked:
                    logger.warning("Revoked token usage", jti=jti)
                    raise InvalidTokenException("Token has been revoked")

                # Check user-level session invalidation (Deactivation / Full Revocation)
                user_invalid_before = await self.redis.get(f"auth:user:{sub}:invalid_before")
                if user_invalid_before and int(raw_claims.get("iat", 0)) < int(user_invalid_before):
                    logger.warning("Revoked token usage (user deactivation)", sub=sub)
                    raise InvalidTokenException("Token revoked due to account status change")

                # Check workspace-level session invalidation (F4.5, F4.6)
                if workspace_id:
                    invalid_before = await self.redis.get(f"auth:user:{sub}:workspace:{workspace_id}:invalid_before")
                    if invalid_before and int(raw_claims.get("iat", 0)) < int(invalid_before):
                        logger.warning("Revoked token usage (workspace permissions changed)", sub=sub, workspace=workspace_id)
                        raise InvalidTokenException("Token revoked due to workspace permission changes")

            return TokenPayload(
                sub=sub,
                email=raw_claims.get("email"),  # AUTH-009: read email claim from token payload
                role=str(raw_claims.get("role", "viewer")),
                tenant_id=raw_claims.get("tenant_id"),
                workspace_id=workspace_id,
                full_name=None,
                organization_name=None,
                exp=int(raw_claims.get("exp", 0)),
                jti=jti,
                aud=raw_claims.get("aud"),
                iss=raw_claims.get("iss"),
                metadata=raw_claims,
                family_id=raw_claims.get("family_id"),
                demo_simulated=bool(raw_claims.get("demo_simulated", False)),
            )

        except ExpiredSignatureError as e:
            logger.warning("Expired token", error=str(e))
            raise ExpiredTokenException() from e
        except InvalidTokenError as e:
            logger.warning("JWT validation failure", error=str(e))
            raise InvalidTokenException(f"Invalid authentication token: {e!s}") from e

    async def revoke_token(self, jti: str, exp: int) -> None:
        """Adds a token's JTI to the Redis blocklist until it naturally expires."""
        if not self.redis:
            logger.error("Redis is not configured; cannot blocklist token")
            return

        now = int(time.time())
        ttl = exp - now
        if ttl > 0:
            await self.redis.set(f"auth:blocklist:{jti}", "revoked", ex=ttl)
            logger.info("Token blocklisted", jti=jti, ttl=ttl)

    async def revoke_user_workspace_tokens(self, user_id: str, workspace_id: str) -> None:
        """Revokes all active tokens for a user in a specific workspace.

        This satisfies F4.5 and F4.6 active session invalidation.
        Sets an invalid_before timestamp in Redis that tokens must be issued after.
        """
        if not self.redis:
            return

        now = int(time.time())
        key = f"auth:user:{user_id}:workspace:{workspace_id}:invalid_before"
        # 15 minutes TTL because access tokens live for 15 mins.
        # After 15 mins, any old token is naturally expired anyway.
        await self.redis.set(key, str(now), ex=15 * 60)
        logger.info("Workspace tokens revoked", user_id=user_id, workspace_id=workspace_id, invalid_before=now)

    async def revoke_user_tokens(self, user_id: str) -> None:
        """Revokes all active tokens for a user across all workspaces."""
        if not self.redis:
            return

        now = int(time.time())
        key = f"auth:user:{user_id}:invalid_before"
        # 15 minutes TTL because access tokens live for 15 mins.
        await self.redis.set(key, str(now), ex=15 * 60)
        logger.info("All user tokens revoked", user_id=user_id, invalid_before=now)

def get_jwt_service() -> JWTService:
    """Return an instance of the JWTService."""
    return JWTService()
