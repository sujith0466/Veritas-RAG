"""Single Sign-On (SSO) and OIDC Provider integrations.

Implements the provider abstraction and Google OIDC.
"""

import base64
import hashlib
import json
import os
import secrets
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx
import jwt
import structlog

from backend.cache.client import get_redis_client
from backend.core.exceptions.auth import AuthenticationException

logger = structlog.get_logger(__name__)


class SSOProvider(Protocol):
    """Interface for OIDC providers."""

    async def get_auth_url(self, join_intent: dict[str, Any] | None = None) -> str:
        """Generate the authorization URL including state and PKCE."""
        ...

    async def exchange_code(self, code: str, state: str) -> dict[str, Any]:
        """Exchange the auth code for tokens and return user profile."""
        ...


LUA_ATOMIC_CONSUME = """
local val = redis.call('GET', KEYS[1])
if val then
    redis.call('DEL', KEYS[1])
end
return val
"""


async def atomic_consume_state(redis_client: Any, key: str) -> str | None:
    """Atomically consumes and deletes a key from Redis.

    Guarantees that concurrent callback requests cannot both consume the same state,
    preventing TOCTOU replay vulnerabilities.
    """
    try:
        return await redis_client.getdel(key)
    except Exception:
        return await redis_client.eval(LUA_ATOMIC_CONSUME, 1, key)


class GoogleOIDCProvider:
    """Google OpenID Connect integration."""

    def __init__(self) -> None:
        self.client_id = os.getenv("OIDC_GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("OIDC_GOOGLE_CLIENT_SECRET")
        self.redirect_uri = os.getenv("OIDC_GOOGLE_REDIRECT_URI", "http://localhost:8000/api/v1/auth/sso/callback/google")
        self.discovery_url = "https://accounts.google.com/.well-known/openid-configuration"
        self.redis = get_redis_client()

        if not self.client_id or not self.client_secret:
            raise AuthenticationException("OIDC_GOOGLE_CLIENT_ID and OIDC_GOOGLE_CLIENT_SECRET environment variables are required.")

    async def _get_oidc_config(self) -> dict[str, Any]:
        """Fetch OIDC discovery document (in a real app, this should be cached)."""
        # For simplicity, we just fetch it or hardcode the endpoints
        # Hardcoding the known Google endpoints to avoid HTTP calls during init
        return {
            "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_endpoint": "https://oauth2.googleapis.com/token",
            "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
            "issuer": "https://accounts.google.com"
        }

    async def get_auth_url(self, join_intent: dict[str, Any] | None = None) -> str:
        """Generate the authorization URL including state and PKCE."""
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)

        # PKCE
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode("ascii")).digest()
        ).decode("ascii").rstrip("=")

        config = await self._get_oidc_config()

        # Cache state, nonce, verifier, and optional join_intent in Redis for 10 minutes
        if self.redis:
            session_data = {
                "nonce": nonce,
                "code_verifier": code_verifier,
            }
            if join_intent:
                session_data["join_intent"] = join_intent
            await self.redis.set(f"oidc:state:{state}", json.dumps(session_data), ex=600)
        else:
            logger.warning("Redis is not available. OIDC state cannot be verified securely.")

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "access_type": "online",
        }

        auth_url = f"{config['authorization_endpoint']}?{urlencode(params)}"
        return auth_url

    async def _get_jwks(self, client: httpx.AsyncClient, jwks_uri: str, force_refresh: bool = False) -> dict[str, Any]:
        """Fetch and cache provider JWKS with a 1-hour TTL."""
        cache_key = "oidc:jwks:google"
        if not force_refresh and self.redis:
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                logger.warning("Failed to get JWKS from Redis cache", error=str(e))

        jwks_response = await client.get(jwks_uri)
        if jwks_response.status_code != 200:
            raise AuthenticationException("Failed to fetch provider JWKS.")
        jwks = jwks_response.json()

        if self.redis:
            try:
                await self.redis.set(cache_key, json.dumps(jwks), ex=3600)
            except Exception as e:
                logger.warning("Failed to store JWKS in Redis cache", error=str(e))

        return jwks

    async def exchange_code(self, code: str, state: str) -> dict[str, Any]:
        """Exchange the auth code for tokens and return user profile."""
        if not self.redis:
            raise AuthenticationException("Redis is required for OIDC state verification.")

        # Atomically verify and consume single-use state
        session_data_json = await atomic_consume_state(self.redis, f"oidc:state:{state}")
        if not session_data_json:
            raise AuthenticationException("Invalid or expired state parameter.")

        session_data = json.loads(session_data_json)
        nonce = session_data["nonce"]
        code_verifier = session_data["code_verifier"]
        join_intent = session_data.get("join_intent")

        config = await self._get_oidc_config()

        # Exchange code for token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                config["token_endpoint"],
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri,
                    "code_verifier": code_verifier,
                },
                headers={"Accept": "application/json"}
            )

            if token_response.status_code != 200:
                logger.error(
                    "OIDC token exchange failed",
                    status_code=token_response.status_code,
                    error_type="oidc_token_exchange_failure",
                )
                raise AuthenticationException("Failed to exchange authorization code.")

            tokens = token_response.json()
            id_token = tokens.get("id_token")

            if not id_token:
                raise AuthenticationException("No ID token returned from provider.")

            # Validate ID token (fetch cached JWKS)
            jwks = await self._get_jwks(client, config["jwks_uri"])

            public_keys = {}
            for jwk in jwks.get("keys", []):
                kid = jwk.get("kid")
                if kid:
                    public_keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

            unverified_header = jwt.get_unverified_header(id_token)
            kid = unverified_header.get("kid")

            # Handle possible key rotation by re-fetching if kid not in cache
            if not kid or kid not in public_keys:
                jwks = await self._get_jwks(client, config["jwks_uri"], force_refresh=True)
                public_keys = {}
                for jwk in jwks.get("keys", []):
                    k = jwk.get("kid")
                    if k:
                        public_keys[k] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

            if not kid or kid not in public_keys:
                raise AuthenticationException("Invalid ID token key ID.")

            try:
                # Validate signature, exp, iat, aud, iss
                payload = jwt.decode(
                    id_token,
                    key=public_keys[kid],
                    algorithms=["RS256"],
                    audience=self.client_id,
                    issuer=[config["issuer"], "accounts.google.com"],
                )
            except jwt.ExpiredSignatureError:
                raise AuthenticationException("ID token expired.")
            except jwt.InvalidTokenError as e:
                logger.warning("ID token validation failed", error=str(e))
                raise AuthenticationException("Invalid ID token.")

            # Validate nonce
            if payload.get("nonce") != nonce:
                raise AuthenticationException("Invalid nonce.")

            # Validate email_verified
            if not payload.get("email_verified"):
                raise AuthenticationException("Email not verified by provider.")

            return {
                "provider": "google",
                "provider_user_id": payload["sub"],
                "email": payload["email"],
                "name": payload.get("name"),
                "picture": payload.get("picture"),
                "join_intent": join_intent,
            }

def get_sso_provider(provider_name: str) -> SSOProvider:
    """Factory to get the correct SSO provider."""
    if provider_name.lower() == "google":
        return GoogleOIDCProvider()
    raise AuthenticationException(f"Unsupported provider: {provider_name}")
