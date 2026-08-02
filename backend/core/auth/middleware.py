"""Authentication helpers and context middleware.

Provides utilities for extracting bearer credentials from HTTP requests
and managing request-scoped context.
"""

from fastapi import Request


def extract_bearer_token(request: Request) -> str | None:
    """Extract and clean Bearer token from the HTTP Authorization header.

    Args:
        request: The incoming FastAPI HTTP request.

    Returns:
        The raw token string if present and properly formatted, else None.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    parts = auth_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]


import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse
import structlog

from backend.core.auth.context import UserContext
from backend.core.exceptions.auth import ExpiredTokenException, InvalidTokenException
from backend.core.permissions.rbac import Role
from backend.core.security.jwt import get_jwt_service

logger = structlog.get_logger(__name__)

class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    """Enterprise JWT Middleware enforcing signature, expiry, and blocklist on all requests."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        token = extract_bearer_token(request)

        if not token:
            # 1. No Authorization header -> Continue request and set request.state.user_context = None
            request.state.user_context = None
            return await call_next(request)

        # 2. & 3. Valid/Invalid Authorization header
        try:
            jwt_service = get_jwt_service()
            # This verifies signature, expiry, audience, issuer, and queries Redis blocklist
            token_payload = await jwt_service.verify_token(token)

            # Populate request context with claims mapped to UserContext
            request.state.user_context = UserContext(
                id=uuid.UUID(token_payload.sub),
                supabase_id=token_payload.sub,
                email=token_payload.email or "",
                role=Role(token_payload.role),
                is_active=True,
                tenant_id=token_payload.tenant_id,
                workspace_name=token_payload.workspace_name
            )

        except ExpiredTokenException:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": {"code": "EXPIRED_TOKEN", "message": "Authentication token has expired"}}
            )
        except InvalidTokenException as e:
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": {"code": "INVALID_TOKEN", "message": str(e)}}
            )
        except Exception as e:
            logger.error("Unexpected error during JWT validation", error=str(e))
            return JSONResponse(
                status_code=401,
                content={"success": False, "error": {"code": "UNAUTHORIZED", "message": "Authentication failed"}}
            )

        return await call_next(request)
