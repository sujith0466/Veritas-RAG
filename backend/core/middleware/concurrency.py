"""SSE Concurrency Limiter Middleware.

Protects the API container from exhaustion and OOMKill by bounding
concurrent active Server-Sent Event (SSE) streaming connections.
"""

import asyncio
import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from backend.core.config import get_settings

logger = structlog.get_logger(__name__)


class SSEConcurrencyLimiterMiddleware(BaseHTTPMiddleware):
    """Enforces global concurrency limits on SSE streaming endpoints."""

    def __init__(
        self,
        app: ASGIApp,
        max_concurrent_streams: int | None = None,
    ) -> None:
        super().__init__(app)
        self._max_concurrent_override = max_concurrent_streams
        self._active_streams = 0
        self._lock = asyncio.Lock()

    def _get_max_concurrent(self) -> int:
        if self._max_concurrent_override is not None:
            return self._max_concurrent_override
        try:
            settings = get_settings()
            return settings.security.max_concurrent_sse_streams
        except Exception:
            return 50

    def _is_sse_request(self, request: Request) -> bool:
        path = request.url.path
        if path.endswith("/stream") or "/stream" in path:
            return True
        accept = request.headers.get("accept", "")
        return "text/event-stream" in accept

    @property
    def active_streams(self) -> int:
        return self._active_streams

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not self._is_sse_request(request):
            return await call_next(request)

        max_limit = self._get_max_concurrent()

        async with self._lock:
            if self._active_streams >= max_limit:
                logger.warning(
                    "SSE concurrency limit reached; rejecting new stream",
                    active_streams=self._active_streams,
                    max_limit=max_limit,
                    path=request.url.path,
                )
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Too many concurrent streaming connections. Please retry shortly."},
                    headers={"Retry-After": "5"},
                )
            self._active_streams += 1

        try:
            return await call_next(request)
        finally:
            async with self._lock:
                self._active_streams = max(0, self._active_streams - 1)
