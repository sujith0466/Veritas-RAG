"""Unit tests for enterprise SecureWebFetcher service and response stream bounds."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from backend.document.services.url_security import (
    SSRFSafeUrlValidator,
    SSRFSecurityException,
    ValidatedDestinationDTO,
)
from backend.document.services.web_fetcher import (
    FetchedWebResultDTO,
    SecureWebFetcher,
    WebFetchException,
)


@pytest.fixture
def safe_destination() -> ValidatedDestinationDTO:
    return ValidatedDestinationDTO(
        url="https://example.com/page",
        scheme="https",
        host="example.com",
        port=443,
        path_and_query="/page",
        resolved_ips=["93.184.216.34"],
        pinned_ip="93.184.216.34",
    )


class TestSecureWebFetcherBasics:
    """Tests for basic fetch execution, content-types, and headers."""

    @pytest.mark.asyncio
    async def test_successful_https_fetch(self, safe_destination: ValidatedDestinationDTO) -> None:
        html_content = b"<!DOCTYPE html><html><body><h1>Knowledge Document</h1></body></html>"
        mock_response = httpx.Response(
            status_code=200,
            headers={"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(html_content))},
            content=html_content,
        )

        with (
            patch.object(SSRFSafeUrlValidator, "validate_destination", AsyncMock(return_value=safe_destination)),
            patch("backend.document.services.web_fetcher.create_ssrf_safe_client") as mock_client_factory,
        ):
            mock_client = AsyncMock()
            mock_client.build_request.return_value = httpx.Request("GET", "https://example.com/page")
            mock_client.send.return_value = mock_response
            mock_client_factory.return_value.__aenter__.return_value = mock_client

            result: FetchedWebResultDTO = await SecureWebFetcher.fetch_url("https://example.com/page")

            assert result.requested_url == "https://example.com/page"
            assert result.final_url == "https://example.com/page"
            assert result.status_code == 200
            assert result.content_type == "text/html"
            assert result.body_bytes == html_content
            assert result.content_length == len(html_content)
            assert isinstance(result.fetched_at, datetime)
            assert result.fetched_at.tzinfo == UTC

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status_code", [400, 403, 404, 500, 502, 503])
    async def test_http_error_statuses_raise_web_fetch_exception(
        self, safe_destination: ValidatedDestinationDTO, status_code: int
    ) -> None:
        mock_response = httpx.Response(
            status_code=status_code,
            headers={"Content-Type": "text/html"},
            content=b"<html>Error page</html>",
        )

        with (
            patch.object(SSRFSafeUrlValidator, "validate_destination", AsyncMock(return_value=safe_destination)),
            patch("backend.document.services.web_fetcher.create_ssrf_safe_client") as mock_client_factory,
        ):
            mock_client = AsyncMock()
            mock_client.build_request.return_value = httpx.Request("GET", "https://example.com/page")
            mock_client.send.return_value = mock_response
            mock_client_factory.return_value.__aenter__.return_value = mock_client

            with pytest.raises(WebFetchException) as exc:
                await SecureWebFetcher.fetch_url("https://example.com/page")

            assert exc.value.error_code == "FETCH_HTTP_ERROR"
            assert str(status_code) in str(exc.value)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "unsupported_mime",
        [
            "application/pdf",
            "application/octet-stream",
            "image/png",
            "image/jpeg",
            "video/mp4",
            "application/zip",
            "application/x-tar",
        ],
    )
    async def test_unsupported_content_type_rejected(
        self, safe_destination: ValidatedDestinationDTO, unsupported_mime: str
    ) -> None:
        mock_response = httpx.Response(
            status_code=200,
            headers={"Content-Type": unsupported_mime},
            content=b"BINARYDATA",
        )

        with (
            patch.object(SSRFSafeUrlValidator, "validate_destination", AsyncMock(return_value=safe_destination)),
            patch("backend.document.services.web_fetcher.create_ssrf_safe_client") as mock_client_factory,
        ):
            mock_client = AsyncMock()
            mock_client.build_request.return_value = httpx.Request("GET", "https://example.com/page")
            mock_client.send.return_value = mock_response
            mock_client_factory.return_value.__aenter__.return_value = mock_client

            with pytest.raises(WebFetchException) as exc:
                await SecureWebFetcher.fetch_url("https://example.com/page")

            assert exc.value.error_code == "FETCH_UNSUPPORTED_CONTENT_TYPE"
            assert unsupported_mime in str(exc.value)


class TestSecureWebFetcherStreamBounds:
    """Tests for size limits, streaming cutoff, and timeout handling."""

    @pytest.mark.asyncio
    async def test_oversized_content_aborted_during_streaming(
        self, safe_destination: ValidatedDestinationDTO
    ) -> None:
        # Create generator simulating response stream > 10MB
        async def large_stream(chunk_size: int | None = None):
            _ = chunk_size
            chunk = b"X" * (1024 * 1024)  # 1 MB
            for _ in range(12):  # 12 MB total
                yield chunk

        mock_response = httpx.Response(
            status_code=200,
            headers={"Content-Type": "text/html"},
            stream=httpx.ByteStream(b""),
        )
        mock_response.aiter_bytes = large_stream

        with (
            patch.object(SSRFSafeUrlValidator, "validate_destination", AsyncMock(return_value=safe_destination)),
            patch("backend.document.services.web_fetcher.create_ssrf_safe_client") as mock_client_factory,
        ):
            mock_client = AsyncMock()
            mock_client.build_request.return_value = httpx.Request("GET", "https://example.com/page")
            mock_client.send.return_value = mock_response
            mock_client_factory.return_value.__aenter__.return_value = mock_client

            with pytest.raises(WebFetchException) as exc:
                await SecureWebFetcher.fetch_url("https://example.com/page", max_bytes=10 * 1024 * 1024)

            assert exc.value.error_code == "FETCH_CONTENT_TOO_LARGE"
            assert "exceeded maximum limit" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_read_timeout_raises_web_fetch_exception(
        self, safe_destination: ValidatedDestinationDTO
    ) -> None:
        with (
            patch.object(SSRFSafeUrlValidator, "validate_destination", AsyncMock(return_value=safe_destination)),
            patch("backend.document.services.web_fetcher.create_ssrf_safe_client") as mock_client_factory,
        ):
            mock_client = AsyncMock()
            mock_client.build_request.return_value = httpx.Request("GET", "https://example.com/page")
            mock_client.send.side_effect = httpx.ReadTimeout("Read timed out")
            mock_client_factory.return_value.__aenter__.return_value = mock_client

            with pytest.raises(WebFetchException) as exc:
                await SecureWebFetcher.fetch_url("https://example.com/page")

            assert exc.value.error_code == "FETCH_TIMEOUT"

    @pytest.mark.asyncio
    async def test_connect_timeout_raises_web_fetch_exception(
        self, safe_destination: ValidatedDestinationDTO
    ) -> None:
        with (
            patch.object(SSRFSafeUrlValidator, "validate_destination", AsyncMock(return_value=safe_destination)),
            patch("backend.document.services.web_fetcher.create_ssrf_safe_client") as mock_client_factory,
        ):
            mock_client = AsyncMock()
            mock_client.build_request.return_value = httpx.Request("GET", "https://example.com/page")
            mock_client.send.side_effect = httpx.ConnectTimeout("Connection refused / timed out")
            mock_client_factory.return_value.__aenter__.return_value = mock_client

            with pytest.raises(WebFetchException) as exc:
                await SecureWebFetcher.fetch_url("https://example.com/page")

            assert exc.value.error_code == "FETCH_CONNECTION_ERROR"


class TestSecureWebFetcherRedirects:
    """Tests for multi-hop redirect handling, loop prevention, and SSRF interception."""

    @pytest.mark.asyncio
    async def test_successful_two_hop_redirect(self, safe_destination: ValidatedDestinationDTO) -> None:
        dest_hop1 = safe_destination
        dest_hop2 = ValidatedDestinationDTO(
            url="https://example.com/docs/final",
            scheme="https",
            host="example.com",
            port=443,
            path_and_query="/docs/final",
            resolved_ips=["93.184.216.34"],
            pinned_ip="93.184.216.34",
        )

        resp1 = httpx.Response(status_code=301, headers={"Location": "/docs/final"})
        resp2 = httpx.Response(
            status_code=200,
            headers={"Content-Type": "text/html"},
            content=b"<html>Final Doc</html>",
        )

        with (
            patch.object(SSRFSafeUrlValidator, "validate_destination", AsyncMock(side_effect=[dest_hop1, dest_hop2])),
            patch("backend.document.services.web_fetcher.create_ssrf_safe_client") as mock_client_factory,
        ):
            mock_client = AsyncMock()
            mock_client.build_request.side_effect = [
                httpx.Request("GET", "https://example.com/page"),
                httpx.Request("GET", "https://example.com/docs/final"),
            ]
            mock_client.send.side_effect = [resp1, resp2]
            mock_client_factory.return_value.__aenter__.return_value = mock_client

            result = await SecureWebFetcher.fetch_url("https://example.com/page")
            assert result.requested_url == "https://example.com/page"
            assert result.final_url == "https://example.com/docs/final"
            assert result.status_code == 200
            assert result.body_bytes == b"<html>Final Doc</html>"
            assert len(result.redirect_chain) == 2

    @pytest.mark.asyncio
    async def test_redirect_to_private_ip_fails_closed(self, safe_destination: ValidatedDestinationDTO) -> None:
        # Public page issues redirect to internal cloud metadata IP
        resp1 = httpx.Response(status_code=302, headers={"Location": "https://169.254.169.254/latest/meta-data"})

        with (
            patch.object(
                SSRFSafeUrlValidator,
                "validate_destination",
                AsyncMock(side_effect=[
                    safe_destination,
                    SSRFSecurityException(error_code="SSRF_IP_BLOCKED", message="Blocked IP 169.254.169.254"),
                ]),
            ),
            patch("backend.document.services.web_fetcher.create_ssrf_safe_client") as mock_client_factory,
        ):
            mock_client = AsyncMock()
            mock_client.build_request.return_value = httpx.Request("GET", "https://example.com/page")
            mock_client.send.return_value = resp1
            mock_client_factory.return_value.__aenter__.return_value = mock_client

            with pytest.raises(SSRFSecurityException) as exc:
                await SecureWebFetcher.fetch_url("https://example.com/page")

            assert exc.value.error_code == "SSRF_IP_BLOCKED"

    @pytest.mark.asyncio
    async def test_redirect_loop_detected(self, safe_destination: ValidatedDestinationDTO) -> None:
        # Page redirects to itself
        resp1 = httpx.Response(status_code=302, headers={"Location": "https://example.com/page"})

        with (
            patch.object(SSRFSafeUrlValidator, "validate_destination", AsyncMock(return_value=safe_destination)),
            patch("backend.document.services.web_fetcher.create_ssrf_safe_client") as mock_client_factory,
        ):
            mock_client = AsyncMock()
            mock_client.build_request.return_value = httpx.Request("GET", "https://example.com/page")
            mock_client.send.return_value = resp1
            mock_client_factory.return_value.__aenter__.return_value = mock_client

            with pytest.raises(WebFetchException) as exc:
                await SecureWebFetcher.fetch_url("https://example.com/page")

            assert exc.value.error_code == "FETCH_REDIRECT_LOOP"

    @pytest.mark.asyncio
    async def test_https_to_http_downgrade_redirect_rejected(
        self, safe_destination: ValidatedDestinationDTO
    ) -> None:
        resp1 = httpx.Response(status_code=301, headers={"Location": "http://example.com/insecure"})

        with (
            patch.object(SSRFSafeUrlValidator, "validate_destination", AsyncMock(return_value=safe_destination)),
            patch("backend.document.services.web_fetcher.create_ssrf_safe_client") as mock_client_factory,
        ):
            mock_client = AsyncMock()
            mock_client.build_request.return_value = httpx.Request("GET", "https://example.com/page")
            mock_client.send.return_value = resp1
            mock_client_factory.return_value.__aenter__.return_value = mock_client

            with pytest.raises(SSRFSecurityException) as exc:
                await SecureWebFetcher.fetch_url("https://example.com/page")

            assert exc.value.error_code == "SSRF_REDIRECT_FORBIDDEN"
            assert "downgrade" in str(exc.value).lower()
