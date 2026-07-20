"""Security response headers middleware.

Adds hardened HTTP response headers to every response.
These headers are a baseline defence-in-depth measure and do not replace
proper authentication/authorization.

Headers added:
- X-Content-Type-Options: nosniff     — prevents MIME sniffing
- X-Frame-Options: DENY               — prevents clickjacking
- X-XSS-Protection: 0                 — tells modern browsers not to use buggy XSS filter
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy                  — disable unused browser features
- Cache-Control (for API responses)   — prevent caching of sensitive responses

Note: HSTS (Strict-Transport-Security) is intentionally NOT set here —
it must be managed at the reverse proxy / load balancer level in production,
since it requires HTTPS to be meaningful.
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject security headers on every HTTP response."""

    def __init__(self, app: ASGIApp, is_production: bool = False) -> None:
        super().__init__(app)
        self._is_production = is_production

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Disable legacy XSS filter (modern browsers prefer CSP)
        response.headers["X-XSS-Protection"] = "0"
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Permissions policy — disable features not used by this API
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )
        # Prevent caching of API responses
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"

        if self._is_production:
            # HSTS — only in production where HTTPS is guaranteed
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response
