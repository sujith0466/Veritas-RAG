"""Trusted Proxy and Client IP Resolution Middleware.

Safely resolves client IP addresses behind reverse proxies by validating
trusted proxy networks and stripping verified hops from X-Forwarded-For.
Protects against IP spoofing from untrusted direct clients.
"""

import ipaddress
import time
from typing import Sequence
import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from backend.core.config import get_settings

logger = structlog.get_logger(__name__)


class TrustedProxyMiddleware(BaseHTTPMiddleware):
    """Resolve true client IP by safely inspecting X-Forwarded-For behind verified proxies."""

    def __init__(
        self,
        app: ASGIApp,
        trusted_proxies: Sequence[ipaddress.IPv4Network | ipaddress.IPv6Network] | None = None,
        cache_ttl_seconds: float = 60.0,
    ) -> None:
        super().__init__(app)
        self._trusted_proxies = trusted_proxies
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cached_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] | None = None
        self._last_resolved_time: float = 0.0

    def _get_trusted_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        if self._trusted_proxies is not None:
            return list(self._trusted_proxies)

        now = time.monotonic()
        if (
            self._cached_networks is not None
            and (now - self._last_resolved_time) < self._cache_ttl_seconds
        ):
            return self._cached_networks

        try:
            settings = get_settings()
            networks = settings.security.trusted_proxy_networks
        except Exception as e:
            logger.warning("trusted_proxy_settings_load_failed", error=str(e))
            networks = [ipaddress.ip_network("127.0.0.1/32"), ipaddress.ip_network("::1/128")]

        self._cached_networks = networks
        self._last_resolved_time = now
        return networks

    def _is_ip_in_networks(
        self, ip_str: str, networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network]
    ) -> bool:
        try:
            ip = ipaddress.ip_address(ip_str.strip())
            return any(ip in net for net in networks)
        except ValueError:
            return False

    def resolve_client_ip(self, request: Request) -> str:
        peer_host = request.client.host if request.client else "127.0.0.1"
        trusted_networks = self._get_trusted_networks()

        # If direct peer is NOT a trusted proxy, ignore all forwarding headers (anti-spoofing)
        if not self._is_ip_in_networks(peer_host, trusted_networks):
            return peer_host

        # Direct peer is trusted. Inspect X-Forwarded-For
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if not x_forwarded_for:
            # Check X-Real-IP if X-Forwarded-For is missing
            x_real_ip = request.headers.get("X-Real-IP")
            if x_real_ip:
                try:
                    ipaddress.ip_address(x_real_ip.strip())
                    return x_real_ip.strip()
                except ValueError:
                    pass
            return peer_host

        # Parse hops in X-Forwarded-For (comma-separated list)
        raw_hops = [h.strip() for h in x_forwarded_for.split(",") if h.strip()]
        if not raw_hops:
            return peer_host

        # Walk right-to-left: strip trusted proxy hops. First untrusted IP is the client
        for hop in reversed(raw_hops):
            try:
                ip_obj = ipaddress.ip_address(hop)
            except ValueError:
                # Malformed IP in forwarding header; skip invalid token
                continue

            if not any(ip_obj in net for net in trusted_networks):
                return str(ip_obj)

        # All hops were trusted proxies; fall back to the first hop (leftmost) if valid
        try:
            ipaddress.ip_address(raw_hops[0])
            return raw_hops[0]
        except ValueError:
            return peer_host

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        client_ip = self.resolve_client_ip(request)
        request.state.client_ip = client_ip
        return await call_next(request)
