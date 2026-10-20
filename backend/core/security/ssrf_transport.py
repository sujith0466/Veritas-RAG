"""SSRF-Protected HTTP Transport for Webhook Delivery.

Provides connection-time DNS validation, address pinning, and SSRF prevention
while preserving full TLS certificate verification, SNI, and HTTP Host header integrity.
Protects against DNS rebinding (TOCTOU) attacks on outbound webhook delivery.
"""

from collections.abc import Iterable
import ipaddress
import socket
import ssl
from typing import Any

import httpcore
import httpx


class SSRFValidationError(Exception):
    """Raised when an outbound webhook target resolves to a prohibited IP address."""
    pass


PROHIBITED_METADATA_NETWORKS: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = (
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("fd00::/8"),
)


def is_safe_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Evaluates whether an IP address is safe for outbound webhook delivery.
    
    Rejects:
    - Cloud instance metadata endpoints (169.254.169.254)
    - Loopback addresses (127.0.0.0/8, ::1)
    - RFC 1918 private IPv4 addresses (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
    - Unique local IPv6 addresses (fc00::/7)
    - Link-local addresses (169.254.0.0/16, fe80::/10)
    - Multicast addresses (224.0.0.0/4, ff00::/8)
    - Unspecified addresses (0.0.0.0, ::)
    - IPv4-mapped IPv6 addresses wrapping any prohibited IPv4 range
    """
    # Unpack IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1 or ::ffff:169.254.169.254)
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
        ip_obj = ip_obj.ipv4_mapped

    # Explicit check for AWS/GCP/Azure/OpenStack metadata IP
    if str(ip_obj) == "169.254.169.254":
        return False

    # Explicit check for prohibited metadata and carrier-grade NAT / unique local CIDR ranges
    for prohibited_net in PROHIBITED_METADATA_NETWORKS:
        if ip_obj.version == prohibited_net.version and ip_obj in prohibited_net:
            return False

    # Block non-routable / private / internal scopes
    if (
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
    ):
        return False

    # Handle reserved IPs: Allow Well-Known NAT64 Prefix (64:ff9b::/96 per RFC 6052)
    # if the embedded IPv4 address is globally routable
    if ip_obj.is_reserved:
        if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj in ipaddress.IPv6Network("64:ff9b::/96"):
            embedded_ipv4 = ipaddress.IPv4Address(ip_obj.packed[-4:])
            return is_safe_ip(embedded_ipv4)
        return False

    return True


class SSRFProtectedAsyncBackend(httpcore.AsyncNetworkBackend):
    """Network backend that performs DNS validation and IP pinning at TCP connection time.
    
    Prevents time-of-check to time-of-use (TOCTOU) DNS rebinding attacks by ensuring
    that socket creation connects directly to a validated IP rather than re-querying DNS.
    """

    def __init__(self, default_backend: httpcore.AsyncNetworkBackend | None = None):
        self._default = default_backend or httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[tuple[int, int, int | bytes]] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        try:
            addr_info = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror as e:
            raise SSRFValidationError(f"Could not resolve host '{host}': {e}") from e

        if not addr_info:
            raise SSRFValidationError(f"No IP addresses resolved for host '{host}'")

        safe_ips: list[str] = []
        for _family, _socktype, _proto, _canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
            except ValueError as e:
                raise SSRFValidationError(f"Invalid resolved IP '{ip_str}' for host '{host}'") from e

            if not is_safe_ip(ip_obj):
                raise SSRFValidationError(
                    f"Connection refused: host '{host}' resolved to prohibited or private IP '{ip_str}'"
                )
            safe_ips.append(ip_str)

        # Pin connection to the first validated IP address
        pinned_ip = safe_ips[0]
        return await self._default.connect_tcp(
            host=pinned_ip,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[tuple[int, int, int | bytes]] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        raise SSRFValidationError("Unix domain sockets are prohibited for outbound webhook delivery.")

    async def sleep(self, seconds: float) -> None:
        await self._default.sleep(seconds)


class SSRFProtectedTransport(httpx.AsyncBaseTransport):
    """Custom httpx transport that wraps httpcore.AsyncConnectionPool with SSRFProtectedAsyncBackend.
    
    Ensures that:
    1. All outbound TCP connections resolve and pin safe destination IP addresses.
    2. TLS certificate verification, SNI (server_hostname), and HTTP Host headers are preserved.
    """

    def __init__(
        self,
        verify: bool | ssl.SSLContext = True,
        max_connections: int = 10,
        keepalive_expiry: float = 5.0,
    ):
        self._network_backend = SSRFProtectedAsyncBackend()
        ssl_context = (
            httpx.create_ssl_context(verify=verify)
            if not isinstance(verify, ssl.SSLContext)
            else verify
        )
        self._pool = httpcore.AsyncConnectionPool(
            network_backend=self._network_backend,
            ssl_context=ssl_context,
            max_connections=max_connections,
            keepalive_expiry=keepalive_expiry,
            http1=True,
            http2=False,
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        method = request.method.encode("ascii")
        url = httpcore.URL(
            scheme=request.url.raw_scheme,
            host=request.url.raw_host,
            port=request.url.port,
            target=request.url.raw_path,
        )
        headers = [(k.lower(), v) for k, v in request.headers.raw]
        content = request.stream

        core_request = httpcore.Request(
            method=method,
            url=url,
            headers=headers,
            content=content,
            extensions=request.extensions,
        )

        try:
            core_response = await self._pool.handle_async_request(core_request)
        except SSRFValidationError:
            raise
        except Exception as e:
            # Propagate connection errors cleanly
            raise e

        return httpx.Response(
            status_code=core_response.status,
            headers=core_response.headers,
            content=core_response.stream,
            extensions=core_response.extensions,
            request=request,
        )

    async def aclose(self) -> None:
        await self._pool.aclose()
