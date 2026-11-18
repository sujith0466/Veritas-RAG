"""Workspace Provisioning Readiness Middleware (WP-10 / ADR-005 / Option 2).

Enforces that workspaces must be in 'READY' provisioning status before accepting:
- Document uploads and ingestion (/api/v1/documents/upload, /api/v1/documents/process, etc.)
- Chat sessions and messages (/api/v1/chat/*)
- AI generation and retrieval (/api/v1/generation/*, /api/v1/ai/*, /api/v1/retrieval/*)

Returns:
- HTTP 423 Locked when provisioning is PENDING, PROVISIONING, FAILED, or SUSPENDED.
- HTTP 404 Not Found when target workspace does not exist or is inactive (fail closed).
- HTTP 503 Service Unavailable when readiness infrastructure check fails (fail closed).

Bypasses platform admin diagnostic routes (/api/v1/platform/*, /api/v1/platform-admin/*),
health checks, settings, and auth endpoints.
Preserves Protected File #4 (backend/document/api/routes.py) 100% unchanged.
"""

from __future__ import annotations

import posixpath
import re
import uuid
from typing import Any
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
import structlog
from sqlalchemy import select

from backend.core.permissions.rbac import Role
from backend.models.entities.workspace import Workspace, ProvisioningStatus

logger = structlog.get_logger(__name__)

# Explicit bypass route prefixes (lowercase, normalized)
BYPASS_ROUTE_PREFIXES = (
    "/api/v1/platform-admin",
    "/api/v1/platform",
    "/api/v1/auth",
    "/api/v1/health",
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def normalize_path(path: str) -> str:
    """Normalize URI path resolving redundant slashes and relative segments."""
    cleaned = re.sub(r"/+", "/", path)
    norm = posixpath.normpath(cleaned)
    if not norm.startswith("/"):
        norm = "/" + norm
    return norm.lower()


def is_route_covered(path: str, method: str) -> bool:
    """Determine whether the incoming request path is protected by the provisioning guard."""
    norm_path = normalize_path(path)

    for prefix in BYPASS_ROUTE_PREFIXES:
        if norm_path == prefix or norm_path.startswith(f"{prefix}/"):
            return False

    if "/settings" in norm_path:
        return False

    # Document upload & ingestion
    if (
        norm_path.startswith("/api/v1/documents/upload")
        or norm_path.startswith("/api/v1/documents/process")
        or norm_path.startswith("/api/v1/documents/url")
    ):
        return True

    # Mutating document root operations
    if norm_path in ("/api/v1/documents", "/api/v1/documents/") and method.upper() in ("POST", "PUT"):
        return True

    # Chat, AI generation, and retrieval
    if norm_path == "/api/v1/chat" or norm_path.startswith("/api/v1/chat/"):
        # Streaming and active AI query endpoints are always covered regardless of method
        if "stream" in norm_path:
            return True
        # Mutating operations (session creation, message posting, deletion, feedback) require READY workspace
        if method.upper() in ("POST", "PUT", "DELETE", "PATCH"):
            return True
        # Read-only historical chat listing and message reading (GET) are exempt from readiness lock
        if method.upper() == "GET":
            return False
        return True
    if norm_path == "/api/v1/generation" or norm_path.startswith("/api/v1/generation/"):
        return True
    if norm_path == "/api/v1/ai" or norm_path.startswith("/api/v1/ai/"):
        return True
    if norm_path == "/api/v1/retrieval" or norm_path.startswith("/api/v1/retrieval/"):
        return True

    return False


class WorkspaceProvisioningGuardMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware enforcing workspace provisioning readiness (HTTP 423)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        method = request.method

        if not is_route_covered(path, method):
            return await call_next(request)

        # 1. Extract target workspace ID from request context, headers, or query params
        user_context = getattr(request.state, "user_context", None)
        ws_id_str: str | None = None
        if user_context and getattr(user_context, "tenant_id", None):
            ws_id_str = str(user_context.tenant_id)
        elif request.headers.get("X-Workspace-ID"):
            ws_id_str = request.headers.get("X-Workspace-ID")
        elif request.headers.get("X-Tenant-ID"):
            ws_id_str = request.headers.get("X-Tenant-ID")
        elif request.query_params.get("workspace_id"):
            ws_id_str = request.query_params.get("workspace_id")

        if not ws_id_str:
            # Unauthenticated or workspace-less requests pass through to downstream auth guards (401/403)
            return await call_next(request)

        try:
            ws_uuid = uuid.UUID(ws_id_str)
        except (ValueError, TypeError):
            # Malformed workspace ID passes through to standard validation
            return await call_next(request)

        # 2. Check provisioning status (support app.state mock for testing)
        prov_status: str | None = None
        app_mock = getattr(request.app.state, "mock_workspace_provisioning_status", None)
        if isinstance(app_mock, dict):
            prov_status = app_mock.get(ws_uuid) or app_mock.get(str(ws_uuid))
        elif isinstance(app_mock, str):
            prov_status = app_mock

        if prov_status is None:
            try:
                from backend.database.engine import get_session_factory
                session_factory = get_session_factory()
                async with session_factory() as session:
                    stmt = select(Workspace.provisioning_status).where(
                        Workspace.id == ws_uuid,
                        Workspace.deleted_at.is_(None),
                    )
                    res = await session.execute(stmt)
                    prov_status = res.scalar_one_or_none()
            except Exception as e:
                correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
                logger.error(
                    "Workspace provisioning status query failed due to infrastructure error; failing closed",
                    workspace_id=str(ws_uuid),
                    error=str(e),
                )
                return JSONResponse(
                    status_code=503,
                    content={
                        "success": False,
                        "error": {
                            "code": "WORKSPACE_READINESS_UNAVAILABLE",
                            "message": "Workspace readiness check temporarily unavailable. Please retry.",
                            "detail": "Infrastructure error during readiness verification.",
                            "request_id": correlation_id,
                        },
                    },
                    headers={"X-Correlation-ID": correlation_id},
                )

        # 3. Fail closed if workspace does not exist or was deleted
        if prov_status is None:
            correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
            logger.warning(
                "Blocked request to non-existent or inactive workspace",
                workspace_id=str(ws_uuid),
                path=path,
            )
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": {
                        "code": "WORKSPACE_NOT_FOUND",
                        "message": "Target workspace not found or inactive.",
                        "detail": {
                            "workspace_id": str(ws_uuid),
                        },
                        "request_id": correlation_id,
                    },
                },
                headers={"X-Correlation-ID": correlation_id},
            )

        # 4. Enforce READY state
        if prov_status.strip().upper() != ProvisioningStatus.READY.value:
            correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
            logger.info(
                "Blocked request to unready workspace",
                workspace_id=str(ws_uuid),
                status=prov_status,
                path=path,
            )
            return JSONResponse(
                status_code=423,
                content={
                    "success": False,
                    "error": {
                        "code": "WORKSPACE_PROVISIONING_LOCKED",
                        "message": (
                            "Workspace is currently provisioning. Access to document ingestion "
                            "and RAG querying is locked until provisioning is READY."
                        ),
                        "detail": {
                            "workspace_id": str(ws_uuid),
                            "provisioning_status": prov_status,
                        },
                        "request_id": correlation_id,
                    },
                },
                headers={"X-Correlation-ID": correlation_id},
            )

        return await call_next(request)
