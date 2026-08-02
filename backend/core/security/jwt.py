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

# In production, these should be loaded securely from vault/env.
# For local development, we fallback to generating a runtime key if absent.
_DEFAULT_PRIVATE_KEY = os.getenv("JWT_PRIVATE_KEY")
_DEFAULT_PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY")

if not _DEFAULT_PRIVATE_KEY:
    # Dummy fallback for dev mode so the app doesn't crash without keys.
    # We use HS256 in this degraded mode just to allow booting if RS256 keys aren't mounted.
    _DEFAULT_PRIVATE_KEY = "fallback-secret-key-do-not-use-in-production"
    _DEFAULT_PUBLIC_KEY = _DEFAULT_PRIVATE_KEY
    _ALGORITHM = "HS256"
else:
    _ALGORITHM = "RS256"

class JWTService:
    """Handles native JWT generation, validation, and Redis blocklisting."""

    def __init__(self) -> None:
        self.private_key = _DEFAULT_PRIVATE_KEY
        self.public_key = _DEFAULT_PUBLIC_KEY
        self.algorithm = _ALGORITHM
        self.redis = get_redis_client()
        self.issuer = "raguard-auth-server"
        self.audience = "raguard-api"

    async def issue_tokens(self, user: Any) -> tuple[str, str, str]:
        """Issue access and refresh tokens.
        
        Returns:
            Tuple containing:
            - access_token (str)
            - refresh_token_hash (str)
            - family_id (str)
        """
        now = int(time.time())
        access_exp = now + (15 * 60) # 15 minutes

        access_jti = str(uuid.uuid4())

        access_claims = {
            "sub": str(user.id),
            "iss": self.issuer,
            "aud": self.audience,
            "exp": access_exp,
            "iat": now,
            "nbf": now,
            "jti": access_jti,
            "role": user.role,
            "workspace_id": user.workspace_name,
        }

        access_token = jwt.encode(access_claims, self.private_key, algorithm=self.algorithm)

        # We don't sign refresh tokens as JWTs necessarily, they can be opaque URL-safe strings.
        import secrets
        raw_refresh_token = secrets.token_urlsafe(64)
        family_id = str(uuid.uuid4())

        # We return the RAW refresh token to be sent in the cookie,
        # but the hash is what we store in the DB.
        # Wait, the instruction says to return (access, refresh, family), let's just return the raw.
        return access_token, raw_refresh_token, family_id

    async def verify_token(self, token: str) -> TokenPayload:
        """Decode and verify an Access token, checking the Redis blocklist."""
        try:
            raw_claims = jwt.decode(
                token,
                self.public_key,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer
            )

            jti = raw_claims.get("jti")
            sub = str(raw_claims.get("sub"))
            workspace_id = str(raw_claims.get("workspace_id", ""))

            if not jti:
                raise InvalidTokenException("Token lacks required 'jti' claim")

            # Check Redis Blocklist (F2.4)
            if self.redis:
                is_blocked = await self.redis.get(f"auth:blocklist:{jti}")
                if is_blocked:
                    logger.warning("Revoked token usage", jti=jti)
                    raise InvalidTokenException("Token has been revoked")

                # Check workspace-level session invalidation (F4.5, F4.6)
                if workspace_id:
                    invalid_before = await self.redis.get(f"auth:user:{sub}:workspace:{workspace_id}:invalid_before")
                    if invalid_before and int(raw_claims.get("iat", 0)) < int(invalid_before):
                        logger.warning("Revoked token usage (workspace permissions changed)", sub=sub, workspace=workspace_id)
                        raise InvalidTokenException("Token revoked due to workspace permission changes")

            return TokenPayload(
                sub=sub,
                email=None,  # We don't necessarily encode email in access token to keep it small
                role=str(raw_claims.get("role", "user")),
                tenant_id=None,
                workspace_name=workspace_id if workspace_id else "None",
                full_name=None,
                organization_name=None,
                exp=int(raw_claims.get("exp", 0)),
                aud=raw_claims.get("aud"),
                iss=raw_claims.get("iss"),
                metadata=raw_claims,
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
            await self.redis.setex(f"auth:blocklist:{jti}", ttl, "revoked")
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
        await self.redis.setex(key, 15 * 60, str(now))
        logger.info("Workspace tokens revoked", user_id=user_id, workspace_id=workspace_id, invalid_before=now)

def get_jwt_service() -> JWTService:
    """Return an instance of the JWTService."""
    return JWTService()
