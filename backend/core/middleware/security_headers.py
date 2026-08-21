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
- Content-Security-Policy (CSP)       — strict policy per API vs non-API routes
- Cross-Origin-Opener-Policy          — same-origin isolation
- Cross-Origin-Resource-Policy        — same-origin isolation
- Cache-Control / Pragma / Expires    — prevent caching of sensitive API responses
- Strict-Transport-Security (HSTS)   — production HTTPS enforcement
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
        # Cross-origin policies
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        # Content Security Policy (CSP) & Cache Control
        if request.url.path.startswith("/api/"):
            # Strict API CSP: APIs return data, not executable scripts or frames
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )
            # Prevent caching of API responses
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        else:
            # General / Frontend CSP
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' ws: wss: http: https:; "
                "frame-ancestors 'none';"
            )

        if self._is_production:
            # HSTS — only in production where HTTPS is guaranteed
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        return response
