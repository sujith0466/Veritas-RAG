"""Supabase JWT verification and decoding utility.

Supports dual verification modes:
1. Development/Secret mode: Symmetric (HS256) or asymmetric (RS256) using SUPABASE_JWT_SECRET.
2. Production/JWKS mode: Asymmetric (RS256) fetching keys dynamically via SUPABASE_JWKS_URL.
"""

from functools import lru_cache
from typing import Any

import jwt
import structlog
from jwt.exceptions import (ExpiredSignatureError, InvalidTokenError,
                            PyJWKClientError)

from backend.core.auth.context import TokenPayload
from backend.core.config import get_settings
from backend.core.exceptions.auth import (ExpiredTokenException,
                                          InvalidTokenException)

logger = structlog.get_logger(__name__)


class JWTVerifier:
    """Decodes and verifies Supabase JWT tokens supporting shared secret and JWKS."""

    def __init__(self) -> None:
        self._jwk_client: jwt.PyJWKClient | None = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize JWK client if SUPABASE_JWKS_URL is configured."""
        settings = get_settings()
        if settings.supabase.jwks_url:
            try:
                self._jwk_client = jwt.PyJWKClient(settings.supabase.jwks_url)
                logger.info(
                    "Initialized PyJWKClient for JWKS token verification",
                    jwks_url=settings.supabase.jwks_url,
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize PyJWKClient; will fall back to secret verification",
                    error=str(e),
                )

    def verify_and_decode(self, token: str) -> TokenPayload:
        """Decode and verify a JWT token string.

        Args:
            token: The raw JWT bearer token.

        Returns:
            A validated TokenPayload instance.

        Raises:
            ExpiredTokenException: If the token expiration time is in the past.
            InvalidTokenException: If the token signature or format is invalid.
        """
        settings = get_settings()
        try:
            if self._jwk_client:
                try:
                    signing_key = self._jwk_client.get_signing_key_from_jwt(token)
                    key: Any = signing_key.key
                    algorithms = [settings.supabase.jwt_algorithm, "RS256", "ES256"]
                except PyJWKClientError as e:
                    logger.warning(
                        "JWKS lookup failed; falling back to secret", error=str(e)
                    )
                    key = settings.supabase.jwt_secret
                    algorithms = [settings.supabase.jwt_algorithm, "HS256"]
            else:
                key = settings.supabase.jwt_secret
                algorithms = [settings.supabase.jwt_algorithm, "HS256"]

            raw_claims = jwt.decode(
                token,
                key=key,
                algorithms=algorithms,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": False,
                },
            )

            sub = raw_claims.get("sub")
            if not sub:
                raise InvalidTokenException("Token lacks required 'sub' claim")

            # Extract email and role from claims or Supabase metadata structures
            user_metadata = raw_claims.get("user_metadata")
            if not isinstance(user_metadata, dict):
                user_metadata = {}
            app_metadata = raw_claims.get("app_metadata")
            if not isinstance(app_metadata, dict):
                app_metadata = {}

            email = raw_claims.get("email") or user_metadata.get("email")
            role_claim = (
                raw_claims.get("role")
                or app_metadata.get("role")
                or user_metadata.get("role")
                or "viewer"
            )
            tenant_id = (
                raw_claims.get("tenant_id")
                or app_metadata.get("tenant_id")
                or user_metadata.get("tenant_id")
            )
            workspace_name = (
                raw_claims.get("workspace_name")
                or app_metadata.get("workspace_name")
                or user_metadata.get("workspace_name")
            )

            return TokenPayload(
                sub=str(sub),
                email=str(email) if email else None,
                role=str(role_claim),
                tenant_id=str(tenant_id) if tenant_id else None,
                workspace_name=str(workspace_name) if workspace_name else None,
                exp=int(raw_claims.get("exp", 0)),
                aud=raw_claims.get("aud"),
                iss=raw_claims.get("iss"),
                metadata=raw_claims,
            )

        except ExpiredSignatureError as e:
            logger.debug("Token verification failed: expired signature")
            raise ExpiredTokenException() from e
        except (InvalidTokenError, PyJWKClientError, ValueError) as e:
            logger.debug("Token verification failed: invalid token", error=str(e))
            raise InvalidTokenException(f"Invalid authentication token: {e!s}") from e


@lru_cache(maxsize=1)
def get_jwt_verifier() -> JWTVerifier:
    """Return the singleton instance of the JWTVerifier."""
    return JWTVerifier()
