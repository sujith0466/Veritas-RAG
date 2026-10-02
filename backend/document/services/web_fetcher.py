"""Enterprise Secure Web Fetcher Service for Website Knowledge Ingestion.

Enforces strict network security boundaries established in D4.1:
1. Reuses SSRFSafeUrlValidator and PinToIPTransport.
2. Follows max 3 manual redirect hops with mandatory D4.1 per-hop validation.
3. Strict connect (5s) and read (15s) timeouts.
4. Bounded response streaming (hard 10 MB limit, rejecting oversized bodies in-flight).
5. Content-Type allowlisting (text/html, application/xhtml+xml, text/plain).
6. Sanitized headers: Never leaks ambient auth, cookies, or internal tokens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from backend.core.exceptions.base import RAGuardException
from backend.document.services.url_security import (
    SSRFSafeUrlValidator,
    create_ssrf_safe_client,
    validate_redirect_destination,
)

logger = structlog.get_logger(__name__)


# ============================================================================
# Fetch Exceptions
# ============================================================================


class WebFetchException(RAGuardException):
    """Exception raised during secure web fetching operations."""

    http_status: int = 400

    def __init__(
        self,
        error_code: str,
        message: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=f"[{error_code}] {message}",
            detail=detail,
            error_code=error_code,
        )


# ============================================================================
# Result DTO
# ============================================================================


@dataclass(frozen=True)
class FetchedWebResultDTO:
    """Immutable snapshot of a securely fetched web resource."""

    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    content_length: int | None
    fetched_at: datetime
    body_bytes: bytes
    headers: dict[str, str] = field(default_factory=dict)
    redirect_chain: list[str] = field(default_factory=list)


# ============================================================================
# Secure Web Fetcher Implementation
# ============================================================================


class SecureWebFetcher:
    """High-assurance HTTP client for ingesting remote web documents."""

    MAX_RESPONSE_BYTES: int = 10 * 1024 * 1024  # 10 MB hard limit
    MAX_REDIRECT_HOPS: int = 3
    CONNECT_TIMEOUT_SECONDS: float = 5.0
    READ_TIMEOUT_SECONDS: float = 15.0

    ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
        {
            "text/html",
            "application/xhtml+xml",
            "text/plain",
            "text/xml",
            "application/xml",
        }
    )

    DEFAULT_USER_AGENT: str = "Veritas-RAG-Fetcher/1.0 (+https://raguard.internal)"

    @classmethod
    def sanitize_content_type(cls, raw_content_type: str | None) -> str:
        """Extract and normalize MIME type from Content-Type header."""
        if not raw_content_type:
            return "text/html"  # Default assumption for web endpoints if omitted
        return raw_content_type.split(";")[0].strip().lower()

    @classmethod
    async def fetch_url(  # noqa: PLR0912, PLR0915
        cls,
        url: str,
        user_agent: str | None = None,
        max_bytes: int = MAX_RESPONSE_BYTES,
        allowed_content_types: frozenset[str] | set[str] | None = None,
    ) -> FetchedWebResultDTO:
        """Securely fetch content from a URL with full SSRF and bounds enforcement.

        Args:
            url: The user-supplied URL to fetch.
            user_agent: Optional custom User-Agent string.
            max_bytes: Maximum allowed response body size in bytes (default: 10MB).
            allowed_content_types: Allowlist of permitted MIME types.

        Returns:
            FetchedWebResultDTO containing raw body bytes and fetch metadata.

        Raises:
            WebFetchException: On HTTP error, timeout, oversized content, or security violation.
            SSRFSecurityException: On SSRF or forbidden network destination.
        """
        requested_url = url.strip()
        content_types = allowed_content_types or cls.ALLOWED_CONTENT_TYPES
        ua = user_agent or cls.DEFAULT_USER_AGENT

        # 1. Initial destination validation and IP pinning via D4.1
        current_destination = await SSRFSafeUrlValidator.validate_destination(requested_url)
        redirect_chain: list[str] = [current_destination.url]

        timeout = httpx.Timeout(
            connect=cls.CONNECT_TIMEOUT_SECONDS,
            read=cls.READ_TIMEOUT_SECONDS,
            write=5.0,
            pool=5.0,
        )

        hop_count = 0
        while True:
            # 2. Instantiate pinned, proxy-isolated client for current destination
            async with create_ssrf_safe_client(
                destination=current_destination,
                timeout=timeout,
                verify_ssl=True,
                trust_env=False,
            ) as client:
                request_headers = {
                    "User-Agent": ua,
                    "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Cache-Control": "no-cache",
                }

                try:
                    # Construct request with destination path and query
                    request = client.build_request(
                        method="GET",
                        url=current_destination.url,
                        headers=request_headers,
                    )
                    response = await client.send(request, stream=True)
                except (httpx.ConnectTimeout, httpx.ConnectError) as exc:
                    logger.warning("Web fetch connection failed", url=current_destination.url, error=str(exc))
                    raise WebFetchException(
                        error_code="FETCH_CONNECTION_ERROR",
                        message=f"Failed to connect to destination '{current_destination.host}': {exc}",
                        detail={"url": current_destination.url, "error": str(exc)},
                    ) from exc
                except httpx.ReadTimeout as exc:
                    logger.warning("Web fetch read timed out", url=current_destination.url, error=str(exc))
                    raise WebFetchException(
                        error_code="FETCH_TIMEOUT",
                        message=f"Read operation timed out after {cls.READ_TIMEOUT_SECONDS} seconds.",
                        detail={"url": current_destination.url, "timeout_seconds": cls.READ_TIMEOUT_SECONDS},
                    ) from exc
                except Exception as exc:
                    logger.error("Web fetch unexpected error", url=current_destination.url, error=str(exc))
                    raise WebFetchException(
                        error_code="FETCH_CONNECTION_ERROR",
                        message=f"Unexpected transport error during fetch: {exc}",
                        detail={"url": current_destination.url, "error": str(exc)},
                    ) from exc

                try:
                    status_code = response.status_code

                    # 3. Handle HTTP Redirects (301, 302, 303, 307, 308)
                    if status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("Location")
                        if not location:
                            raise WebFetchException(
                                error_code="FETCH_HTTP_ERROR",
                                message=f"HTTP {status_code} redirect response missing Location header.",
                                detail={"url": current_destination.url, "status_code": status_code},
                            )

                        # Validate redirect destination through D4.1 security gate
                        next_destination = await validate_redirect_destination(
                            current_destination=current_destination,
                            redirect_location=location,
                            hop_count=hop_count,
                            max_hops=cls.MAX_REDIRECT_HOPS,
                            allow_http_downgrade=False,
                        )

                        # Detect redirect loops
                        if next_destination.url in redirect_chain:
                            raise WebFetchException(
                                error_code="FETCH_REDIRECT_LOOP",
                                message=f"Detected cyclic redirect loop targeting '{next_destination.url}'.",
                                detail={"redirect_chain": redirect_chain, "next_url": next_destination.url},
                            )

                        redirect_chain.append(next_destination.url)
                        current_destination = next_destination
                        hop_count += 1
                        continue

                    # 4. Handle HTTP Error Statuses (4xx, 5xx)
                    if status_code >= 400:
                        # Read limited excerpt for diagnostic error detail
                        error_bytes = await response.aread()
                        error_snippet = error_bytes[:512].decode("utf-8", errors="replace")
                        raise WebFetchException(
                            error_code="FETCH_HTTP_ERROR",
                            message=f"Remote server returned HTTP error status {status_code}.",
                            detail={
                                "url": current_destination.url,
                                "status_code": status_code,
                                "response_snippet": error_snippet,
                            },
                        )

                    # 5. Content-Type Validation
                    raw_content_type = response.headers.get("Content-Type")
                    sanitized_mime = cls.sanitize_content_type(raw_content_type)
                    if sanitized_mime not in content_types:
                        raise WebFetchException(
                            error_code="FETCH_UNSUPPORTED_CONTENT_TYPE",
                            message=f"Content-Type '{sanitized_mime}' is not supported for knowledge ingestion.",
                            detail={
                                "url": current_destination.url,
                                "content_type": sanitized_mime,
                                "allowed_content_types": list(content_types),
                            },
                        )

                    # 6. Stream and Enforce Bounded Response Body Size
                    body_chunks: list[bytes] = []
                    total_bytes_read = 0

                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        total_bytes_read += len(chunk)
                        if total_bytes_read > max_bytes:
                            raise WebFetchException(
                                error_code="FETCH_CONTENT_TOO_LARGE",
                                message=f"Response body exceeded maximum limit of {max_bytes} bytes (10 MB).",
                                detail={
                                    "url": current_destination.url,
                                    "bytes_received": total_bytes_read,
                                    "max_bytes": max_bytes,
                                },
                            )
                        body_chunks.append(chunk)

                    body_bytes = b"".join(body_chunks)

                    # Parse Content-Length header if present
                    content_length_hdr = response.headers.get("Content-Length")
                    content_length: int | None = None
                    if content_length_hdr and content_length_hdr.isdigit():
                        content_length = int(content_length_hdr)

                    fetched_at = datetime.now(UTC)

                    # Sanitized response headers map
                    headers_dict = dict(response.headers)

                    return FetchedWebResultDTO(
                        requested_url=requested_url,
                        final_url=current_destination.url,
                        status_code=status_code,
                        content_type=sanitized_mime,
                        content_length=content_length or len(body_bytes),
                        fetched_at=fetched_at,
                        body_bytes=body_bytes,
                        headers=headers_dict,
                        redirect_chain=redirect_chain,
                    )

                finally:
                    await response.aclose()
