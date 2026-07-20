"""Unit tests for ASGI middleware (Correlation ID & Security Headers)."""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
import pytest

from backend.core.middleware import CorrelationIDMiddleware, SecurityHeadersMiddleware


@pytest.mark.unit
class TestCorrelationIDMiddleware:
    @pytest.fixture
    def test_client(self) -> TestClient:
        app = FastAPI()
        app.add_middleware(CorrelationIDMiddleware)

        @app.get("/test-correlation")
        async def endpoint(request: Request) -> dict[str, Any]:
            return {"correlation_id": getattr(request.state, "correlation_id", None)}

        return TestClient(app)

    def test_generates_new_correlation_id_when_missing(self, test_client: TestClient) -> None:
        response = test_client.get("/test-correlation")
        assert response.status_code == 200
        data = response.json()
        assert data["correlation_id"] is not None
        assert response.headers["X-Correlation-ID"] == data["correlation_id"]

    def test_propagates_existing_correlation_id(self, test_client: TestClient) -> None:
        headers = {"X-Correlation-ID": "custom-trace-id-888"}
        response = test_client.get("/test-correlation", headers=headers)
        assert response.status_code == 200
        assert response.json()["correlation_id"] == "custom-trace-id-888"
        assert response.headers["X-Correlation-ID"] == "custom-trace-id-888"


@pytest.mark.unit
class TestSecurityHeadersMiddleware:
    @pytest.fixture
    def app_factory(self) -> Callable[..., FastAPI]:
        def create(is_production: bool = False) -> FastAPI:
            app = FastAPI()
            app.add_middleware(SecurityHeadersMiddleware, is_production=is_production)

            @app.get("/api/v1/secure")
            async def api_endpoint() -> dict[str, Any]:
                return {"status": "ok"}

            @app.get("/page")
            async def web_endpoint() -> dict[str, Any]:
                return {"status": "ok"}

            return app
        return create

    def test_headers_injected_on_non_production(self, app_factory: Callable[..., FastAPI]) -> None:
        client = TestClient(app_factory(is_production=False))
        response = client.get("/page")
        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "0"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Strict-Transport-Security" not in response.headers

    def test_api_cache_control_headers(self, app_factory: Callable[..., FastAPI]) -> None:
        client = TestClient(app_factory(is_production=False))

        # API endpoint should get no-store
        api_resp = client.get("/api/v1/secure")
        assert api_resp.headers["Cache-Control"] == "no-store"
        assert api_resp.headers["Pragma"] == "no-cache"

        # Web/page endpoint should NOT get no-store
        web_resp = client.get("/page")
        assert "Cache-Control" not in web_resp.headers

    def test_hsts_header_in_production(self, app_factory: Callable[..., FastAPI]) -> None:
        client = TestClient(app_factory(is_production=True))
        response = client.get("/api/v1/secure")
        assert response.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
