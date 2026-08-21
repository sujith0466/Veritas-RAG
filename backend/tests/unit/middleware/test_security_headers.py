"""Unit tests for SecurityHeadersMiddleware.

Verifies:
1. Universal security headers (nosniff, DENY, XSS 0, Referrer-Policy, Permissions-Policy, COOP, CORP).
2. Strict API-specific CSP (default-src 'none') and Cache-Control headers on /api/ routes.
3. General Frontend/Landing CSP on non-API routes.
4. Production-only HSTS (Strict-Transport-Security) header injection.
5. Absence of HSTS in development mode.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.middleware.security_headers import SecurityHeadersMiddleware


def create_test_app(is_production: bool = False) -> FastAPI:
    """Create a test FastAPI instance with SecurityHeadersMiddleware."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, is_production=is_production)

    @app.get("/api/v1/resource")
    async def api_resource():
        return {"data": "test"}

    @app.get("/")
    async def root_view():
        return {"page": "landing"}

    return app


@pytest.mark.asyncio
async def test_security_headers_api_route_dev_mode():
    """Verify security headers on API routes in development mode (no HSTS)."""
    app = create_test_app(is_production=False)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/resource")

        assert response.status_code == 200

        # Baseline defensive headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "0"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "camera=()" in response.headers["Permissions-Policy"]
        assert "microphone=()" in response.headers["Permissions-Policy"]
        assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
        assert response.headers["Cross-Origin-Resource-Policy"] == "same-origin"

        # Strict API CSP
        assert response.headers["Content-Security-Policy"] == "default-src 'none'; frame-ancestors 'none'"

        # Cache prevention on API routes
        assert "no-store" in response.headers["Cache-Control"]
        assert "no-cache" in response.headers["Cache-Control"]
        assert response.headers["Pragma"] == "no-cache"
        assert response.headers["Expires"] == "0"

        # HSTS must NOT be set in development mode
        assert "Strict-Transport-Security" not in response.headers


@pytest.mark.asyncio
async def test_security_headers_production_mode_hsts():
    """Verify HSTS header is injected when is_production is True."""
    app = create_test_app(is_production=True)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="https://test") as client:
        response = await client.get("/api/v1/resource")

        assert response.status_code == 200
        assert "Strict-Transport-Security" in response.headers
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts


@pytest.mark.asyncio
async def test_security_headers_non_api_route_csp():
    """Verify frontend / non-API routes receive frontend CSP and do not force no-store."""
    app = create_test_app(is_production=False)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

        assert response.status_code == 200

        # Baseline defensive headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "0"

        # Frontend CSP with self and safe asset sources
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "script-src 'self'" in csp

        # No automatic no-store on static/landing routes
        assert "no-store" not in response.headers.get("Cache-Control", "")
