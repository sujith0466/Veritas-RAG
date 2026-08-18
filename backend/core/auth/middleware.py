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
            from backend.core.security.jwt import get_jwt_service
            jwt_service = get_jwt_service()
            # This verifies signature, expiry, audience, issuer, and queries Redis blocklist
            token_payload = await jwt_service.verify_token(token)
            request.state.token_payload = token_payload

            # Construct the user context from the verified payload to UserContext
            # NOTE: The JWT stores workspace UUID in the `workspace_id` claim (mapped to
            # token_payload.workspace_name). The legacy `tenant_id` claim is never populated.
            # We alias workspace_name → tenant_id so that ChatSession (which stores workspace_id
            # as tenant_id) works without a NOT NULL violation.
            ws_name = token_payload.workspace_name
            effective_tenant_id = (
                ws_name if ws_name and ws_name != "None" else token_payload.tenant_id
            )
            request.state.user_context = UserContext(
                id=uuid.UUID(token_payload.sub),
                email=token_payload.email or "",
                role=Role.from_str(token_payload.role),
                is_active=True,
                tenant_id=effective_tenant_id,
                workspace_name=ws_name,
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
