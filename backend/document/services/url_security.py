"""Enterprise SSRF Protection & DNS-Pinned Transport Service.

Provides cryptographic and network-level security boundaries for remote URL ingestion:
1. Strict scheme allowlisting (HTTP, HTTPS).
2. Standard port enforcement (80, 443).
3. Userinfo (credential) rejection.
4. Comprehensive IPv4 & IPv6 CIDR blacklist validation (RFC 1918, loopback,
   link-local, cloud metadata / IMDS, CGNAT, ULA, multicast, reserved).
5. IPv4-mapped IPv6 and NAT64 extraction and unpacking.
6. Exhaustive DNS resolution of all A and AAAA records via dnspython.
7. Rejection if ANY resolved IP address falls into a forbidden range.
8. Pin-to-IP custom HTTP transport (httpcore backend override) that connects
   directly to the pre-validated IP address while strictly preserving the
   original Host header, TLS SNI (server_hostname), and certificate verification.
   Eliminates DNS Rebinding (TOCTOU) by design.
9. Per-hop redirect interception and validation primitives.
10. Strict timeout boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import socket
import ssl
from typing import Any
import urllib.parse

import dns.asyncresolver
import dns.resolver
import httpcore
from httpcore._backends.auto import AutoBackend
import httpx
import structlog

from backend.core.exceptions.base import RAGuardException

logger = structlog.get_logger(__name__)


# ============================================================================
# Security Exceptions
# ============================================================================


class SSRFSecurityException(RAGuardException):
    """Base exception for all SSRF and network security violations."""

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
# Data Transfer Objects
# ============================================================================


@dataclass(frozen=True)
class ValidatedDestinationDTO:
    """Immutable record of an SSRF-validated network destination."""

    url: str
    scheme: str
    host: str
    port: int
    path_and_query: str
    resolved_ips: list[str]
    pinned_ip: str


# ============================================================================
# SSRF-Safe URL Validator
# ============================================================================


class SSRFSafeUrlValidator:
    """High-assurance validator and DNS inspector for outbound URLs."""

    DEFAULT_ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})
    DEFAULT_ALLOWED_PORTS: frozenset[int] = frozenset({80, 443})
    MAX_URL_LENGTH: int = 2048
    MAX_HOSTNAME_LENGTH: int = 255
    DEFAULT_DNS_TIMEOUT_SECONDS: float = 3.0

    # Exhaustive Blacklisted IPv4 Networks
    FORBIDDEN_IPV4_NETWORKS: tuple[ipaddress.IPv4Network, ...] = (
        ipaddress.IPv4Network("0.0.0.0/8"),  # "This host on this network" / Broadcast
        ipaddress.IPv4Network("10.0.0.0/8"),  # RFC 1918 Private
        ipaddress.IPv4Network("100.64.0.0/10"),  # RFC 6598 Shared Space / CGNAT (Alibaba Metadata 100.100.100.200)
        ipaddress.IPv4Network("127.0.0.0/8"),  # Loopback
        ipaddress.IPv4Network("169.254.0.0/16"),  # Link-Local / Cloud Metadata (169.254.169.254)
        ipaddress.IPv4Network("172.16.0.0/12"),  # RFC 1918 Private
        ipaddress.IPv4Network("192.0.0.0/24"),  # IETF Protocol Assignments
        ipaddress.IPv4Network("192.0.2.0/24"),  # TEST-NET-1 (Documentation)
        ipaddress.IPv4Network("192.168.0.0/16"),  # RFC 1918 Private
        ipaddress.IPv4Network("198.18.0.0/15"),  # Network Interconnect Benchmarking
        ipaddress.IPv4Network("198.51.100.0/24"),  # TEST-NET-2 (Documentation)
        ipaddress.IPv4Network("203.0.113.0/24"),  # TEST-NET-3 (Documentation)
        ipaddress.IPv4Network("224.0.0.0/4"),  # Multicast
        ipaddress.IPv4Network("240.0.0.0/4"),  # Reserved for Future Use
        ipaddress.IPv4Network("255.255.255.255/32"),  # Limited Broadcast
    )

    # Exhaustive Blacklisted IPv6 Networks
    FORBIDDEN_IPV6_NETWORKS: tuple[ipaddress.IPv6Network, ...] = (
        ipaddress.IPv6Network("::/128"),  # Unspecified
        ipaddress.IPv6Network("::1/128"),  # Loopback
        ipaddress.IPv6Network("100::/64"),  # Discard Prefix
        ipaddress.IPv6Network("2001:db8::/32"),  # Documentation
        ipaddress.IPv6Network("fc00::/7"),  # Unique Local Address (ULA)
        ipaddress.IPv6Network("fe80::/10"),  # Link-Local
        ipaddress.IPv6Network("fd00:ec2::254/128"),  # AWS IPv6 IMDS
        ipaddress.IPv6Network("ff00::/8"),  # Multicast
    )

    @classmethod
    def validate_url_syntax(
        cls,
        url: str,
        allowed_schemes: frozenset[str] | set[str] | None = None,
        allowed_ports: frozenset[int] | set[int] | None = None,
    ) -> tuple[str, str, int, str]:
        """Validate URL length, scheme, userinfo, port, and hostname syntax.

        Returns:
            Tuple of (scheme, host, port, path_and_query).

        Raises:
            SSRFSecurityException: If syntax is invalid or violates policy.
        """
        if not url or not isinstance(url, str):
            raise SSRFSecurityException(
                error_code="SSRF_INVALID_URL",
                message="URL must be a non-empty string.",
            )

        trimmed_url = url.strip()
        if len(trimmed_url) > cls.MAX_URL_LENGTH:
            raise SSRFSecurityException(
                error_code="SSRF_INVALID_URL",
                message=f"URL exceeds maximum allowed length of {cls.MAX_URL_LENGTH} characters.",
                detail={"length": len(trimmed_url), "max_length": cls.MAX_URL_LENGTH},
            )

        try:
            parsed = urllib.parse.urlsplit(trimmed_url)
        except ValueError as exc:
            raise SSRFSecurityException(
                error_code="SSRF_INVALID_URL",
                message=f"Malformed URL structure: {exc}",
            ) from exc

        # 1. Scheme Check
        schemes = allowed_schemes or cls.DEFAULT_ALLOWED_SCHEMES
        scheme = (parsed.scheme or "").lower()
        if not scheme:
            raise SSRFSecurityException(
                error_code="SSRF_INVALID_URL",
                message="URL is missing an explicit protocol scheme.",
            )
        if scheme not in schemes:
            raise SSRFSecurityException(
                error_code="SSRF_FORBIDDEN_SCHEME",
                message=f"Scheme '{scheme}' is forbidden. Only {sorted(schemes)} are permitted.",
                detail={"scheme": scheme, "allowed_schemes": list(schemes)},
            )

        # 2. Userinfo (credentials) Check
        if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
            raise SSRFSecurityException(
                error_code="SSRF_USERINFO_NOT_ALLOWED",
                message="URLs containing embedded user credentials (userinfo) are prohibited for security.",
            )

        # 3. Hostname Extraction & Validation
        host = parsed.hostname
        if not host:
            raise SSRFSecurityException(
                error_code="SSRF_INVALID_URL",
                message="URL does not contain a valid hostname.",
            )
        host = host.lower()
        if len(host) > cls.MAX_HOSTNAME_LENGTH:
            raise SSRFSecurityException(
                error_code="SSRF_INVALID_URL",
                message=f"Hostname exceeds maximum length of {cls.MAX_HOSTNAME_LENGTH} characters.",
            )

        # 4. Port Validation
        ports = allowed_ports or cls.DEFAULT_ALLOWED_PORTS
        port = parsed.port
        if port is None:
            port = 443 if scheme == "https" else 80

        if port not in ports:
            raise SSRFSecurityException(
                error_code="SSRF_FORBIDDEN_PORT",
                message=f"Port {port} is not in the allowed ports list: {sorted(ports)}.",
                detail={"port": port, "allowed_ports": list(ports)},
            )

        # 5. Path and Query Assembly
        path = parsed.path or "/"
        path_and_query = path + (f"?{parsed.query}" if parsed.query else "")

        return scheme, host, port, path_and_query

    @classmethod
    def unpack_and_normalize_ip(
        cls, ip: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
        """Unpack IPv4-mapped IPv6 (::ffff:127.0.0.1), NAT64, or 6to4 addresses.

        Returns the underlying IPv4Address when applicable, or the original address.
        """
        if isinstance(ip, ipaddress.IPv6Address):
            # 1. IPv4-mapped IPv6 (::ffff:0:0/96)
            if ip.ipv4_mapped is not None:
                return ip.ipv4_mapped

            # 2. NAT64 well-known prefix (64:ff9b::/96)
            if ip in ipaddress.IPv6Network("64:ff9b::/96"):
                # The lower 32 bits represent the IPv4 address
                return ipaddress.IPv4Address(ip.packed[-4:])

            # 3. 6to4 prefix (2002::/16)
            if ip in ipaddress.IPv6Network("2002::/16"):
                # Bytes 2..6 represent the IPv4 address
                return ipaddress.IPv4Address(ip.packed[2:6])

        return ip

    @classmethod
    def is_ip_forbidden(  # noqa: PLR0911
        cls, ip: ipaddress.IPv4Address | ipaddress.IPv6Address
    ) -> tuple[bool, str]:
        """Check if an IP address belongs to any forbidden range.

        Returns:
            Tuple of (is_forbidden, reason_or_range).
        """
        normalized_ip = cls.unpack_and_normalize_ip(ip)

        # Standard Python IP flags (specific categories first)
        if normalized_ip.is_loopback:
            return True, "Loopback Address"
        if normalized_ip.is_unspecified:
            return True, "Unspecified Address"
        if normalized_ip.is_link_local:
            return True, "Link-Local Address"
        if normalized_ip.is_multicast:
            return True, "Multicast Address"

        # Explicit IPv4 Network Range Inspection
        if isinstance(normalized_ip, ipaddress.IPv4Address):
            for network in cls.FORBIDDEN_IPV4_NETWORKS:
                if normalized_ip in network:
                    return True, f"Forbidden IPv4 Range: {network}"

        # Explicit IPv6 Network Range Inspection
        elif isinstance(normalized_ip, ipaddress.IPv6Network | ipaddress.IPv6Address):
            for network in cls.FORBIDDEN_IPV6_NETWORKS:
                if normalized_ip in network:
                    return True, f"Forbidden IPv6 Range: {network}"

        if normalized_ip.is_reserved:
            return True, "Reserved Address"
        if normalized_ip.is_private:
            return True, "RFC 1918 / Private Address"

        return False, "Allowed Public Address"

    @classmethod
    async def resolve_all_ips(  # noqa: PLR0912
        cls,
        hostname: str,
        timeout: float = DEFAULT_DNS_TIMEOUT_SECONDS,
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        """Resolve all A and AAAA DNS records for a given hostname.

        If hostname is already an IP literal, parses and returns it directly.
        """
        # Case A: Hostname is a literal IP address
        clean_host = hostname.strip("[]")
        try:
            literal_ip = ipaddress.ip_address(clean_host)
            return [literal_ip]
        except ValueError:
            pass

        # Case B: Resolve via dnspython async resolver
        resolved: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
        resolver = dns.asyncresolver.Resolver()
        resolver.lifetime = timeout
        resolver.timeout = timeout

        errors: list[str] = []

        # Resolve A records (IPv4)
        try:
            a_answers = await resolver.resolve(hostname, "A")
            for rdata in a_answers:
                try:
                    resolved.append(ipaddress.IPv4Address(rdata.address))
                except ValueError:
                    continue
        except (
            dns.resolver.NXDOMAIN,
            dns.resolver.NoAnswer,
            dns.resolver.NoNameservers,
            dns.exception.Timeout,
            Exception,
        ) as exc:
            errors.append(f"A record resolution failed: {exc}")

        # Resolve AAAA records (IPv6)
        try:
            aaaa_answers = await resolver.resolve(hostname, "AAAA")
            for rdata in aaaa_answers:
                try:
                    resolved.append(ipaddress.IPv6Address(rdata.address))
                except ValueError:
                    continue
        except (
            dns.resolver.NXDOMAIN,
            dns.resolver.NoAnswer,
            dns.resolver.NoNameservers,
            dns.exception.Timeout,
            Exception,
        ) as exc:
            errors.append(f"AAAA record resolution failed: {exc}")

        # Fallback to asyncio socket.getaddrinfo if dnspython returned no records
        if not resolved:
            try:
                addrinfo = await dns.asyncresolver.get_default_resolver().getaddrinfo(
                    hostname, None, family=socket.AF_UNSPEC
                )
                for res in addrinfo:
                    sockaddr = res[4]
                    ip_str = sockaddr[0]
                    try:
                        resolved.append(ipaddress.ip_address(ip_str))
                    except ValueError:
                        continue
            except Exception:
                pass

        if not resolved:
            raise SSRFSecurityException(
                error_code="SSRF_DNS_RESOLUTION_FAILED",
                message=f"Could not resolve any IP addresses for hostname '{hostname}'.",
                detail={"hostname": hostname, "resolver_errors": errors},
            )

        # Deduplicate resolved IP addresses while preserving order
        unique_ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
        seen: set[str] = set()
        for ip in resolved:
            ip_str = str(ip)
            if ip_str not in seen:
                seen.add(ip_str)
                unique_ips.append(ip)

        return unique_ips

    @classmethod
    async def validate_destination(
        cls,
        url: str,
        allowed_schemes: frozenset[str] | set[str] | None = None,
        allowed_ports: frozenset[int] | set[int] | None = None,
        dns_timeout: float = DEFAULT_DNS_TIMEOUT_SECONDS,
    ) -> ValidatedDestinationDTO:
        """Fully validate URL syntax, resolve all DNS records, and enforce SSRF rules.

        Returns:
            ValidatedDestinationDTO containing verified endpoints and a pinned IP.

        Raises:
            SSRFSecurityException: If any component is invalid or resolves to a forbidden range.
        """
        scheme, host, port, path_and_query = cls.validate_url_syntax(
            url=url,
            allowed_schemes=allowed_schemes,
            allowed_ports=allowed_ports,
        )

        resolved_ips = await cls.resolve_all_ips(hostname=host, timeout=dns_timeout)
        if not resolved_ips:
            raise SSRFSecurityException(
                error_code="SSRF_DNS_RESOLUTION_FAILED",
                message=f"Could not resolve any IP addresses for hostname '{host}'.",
                detail={"hostname": host},
            )

        # Comprehensive validation: Reject if ANY resolved IP address is forbidden
        for ip in resolved_ips:
            is_forbidden, reason = cls.is_ip_forbidden(ip)
            if is_forbidden:
                logger.warning(
                    "SSRF check blocked destination IP",
                    host=host,
                    resolved_ip=str(ip),
                    reason=reason,
                    url=url,
                )
                raise SSRFSecurityException(
                    error_code="SSRF_IP_BLOCKED",
                    message=f"Destination '{host}' resolved to blocked IP address {ip} ({reason}).",
                    detail={
                        "host": host,
                        "blocked_ip": str(ip),
                        "reason": reason,
                    },
                )

        pinned_ip = str(resolved_ips[0])
        canonical_url = f"{scheme}://{host}" + (f":{port}" if (scheme == "http" and port != 80) or (scheme == "https" and port != 443) else "") + path_and_query

        return ValidatedDestinationDTO(
            url=canonical_url,
            scheme=scheme,
            host=host,
            port=port,
            path_and_query=path_and_query,
            resolved_ips=[str(ip) for ip in resolved_ips],
            pinned_ip=pinned_ip,
        )


# ============================================================================
# Pin-to-IP Custom Transport (DNS Rebinding Immunity)
# ============================================================================


class PinToIPBackend(AutoBackend):
    """Network backend override that connects to a specific pinned IP.

    When httpcore performs connect_tcp(host, port), this backend redirects the
    TCP socket connect to `pinned_ip` while letting httpcore retain `host` for
    TLS SNI (server_hostname) and Host header validation.
    """

    def __init__(self, pinned_ip: str) -> None:
        super().__init__()
        self.pinned_ip = pinned_ip

    async def connect_tcp(
        self,
        host: str,  # noqa: ARG002
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> Any:
        # Override connection target with pre-validated pinned IP
        return await super().connect_tcp(
            self.pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


class PinToIPTransport(httpx.AsyncBaseTransport):
    """SSRF-safe custom HTTP transport with pinned IP socket binding.

    Guarantees that the physical connection cannot escape the pre-validated IP,
    completely preventing DNS rebinding and TOCTOU attacks.
    """

    def __init__(
        self,
        pinned_ip: str,
        verify: bool | ssl.SSLContext = True,
        http1: bool = True,
        http2: bool = False,
    ) -> None:
        super().__init__()
        self.pinned_ip = pinned_ip
        self.backend = PinToIPBackend(pinned_ip)
        ssl_context = (
            httpx.create_ssl_context(verify=verify)
            if not isinstance(verify, ssl.SSLContext)
            else verify
        )
        self._pool = httpcore.AsyncConnectionPool(
            network_backend=self.backend,
            ssl_context=ssl_context,
            http1=http1,
            http2=http2,
            retries=0,  # Never silently retry on transport level to prevent socket drift
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        req = httpcore.Request(
            method=request.method.encode(),
            url=httpcore.URL(
                scheme=request.url.scheme.encode(),
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        resp = await self._pool.handle_async_request(req)
        return httpx.Response(
            status_code=resp.status,
            headers=resp.headers,
            stream=httpx.ByteStream(await resp.aread()),
            extensions=resp.extensions,
            request=request,
        )

    async def aclose(self) -> None:
        await self._pool.aclose()


# ============================================================================
# Reusable Redirect & Client Helpers
# ============================================================================


def create_ssrf_safe_client(
    destination: ValidatedDestinationDTO,
    timeout: httpx.Timeout | None = None,
    verify_ssl: bool = True,
    trust_env: bool = False,
) -> httpx.AsyncClient:
    """Create an SSRF-safe httpx.AsyncClient bound to destination.pinned_ip.

    Configured with follow_redirects=False to ensure per-hop redirect validation,
    and trust_env=False to prevent proxy environment hijacking.
    """
    transport = PinToIPTransport(pinned_ip=destination.pinned_ip, verify=verify_ssl)
    default_timeout = timeout or httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
    return httpx.AsyncClient(
        transport=transport,
        timeout=default_timeout,
        follow_redirects=False,  # Enforce per-hop manual redirect interception
        trust_env=trust_env,
    )


async def validate_redirect_destination(
    current_destination: ValidatedDestinationDTO,
    redirect_location: str,
    hop_count: int,
    max_hops: int = 3,
    allow_http_downgrade: bool = False,
) -> ValidatedDestinationDTO:
    """Validate a redirect location URL against SSRF policy.

    Resolves relative URLs against current_destination, disallows HTTPS to HTTP
    downgrade, enforces max redirect hops, and performs full DNS and IP inspection.
    """
    if hop_count >= max_hops:
        raise SSRFSecurityException(
            error_code="SSRF_REDIRECT_FORBIDDEN",
            message=f"Exceeded maximum allowed redirect hops ({max_hops}).",
            detail={"hop_count": hop_count, "max_hops": max_hops},
        )

    # Resolve relative redirects against current destination URL
    resolved_redirect_url = urllib.parse.urljoin(current_destination.url, redirect_location)

    # Disallow HTTPS -> HTTP downgrade unless explicitly allowed
    if (
        current_destination.scheme == "https"
        and not allow_http_downgrade
        and resolved_redirect_url.startswith("http://")
    ):
        raise SSRFSecurityException(
            error_code="SSRF_REDIRECT_FORBIDDEN",
            message="Insecure HTTPS to HTTP redirect downgrade is strictly prohibited.",
            detail={
                "from_url": current_destination.url,
                "to_url": resolved_redirect_url,
            },
        )

    return await SSRFSafeUrlValidator.validate_destination(resolved_redirect_url)


# ============================================================================
# URL Identity Normalizer
# ============================================================================

STANDARD_TRACKING_QUERY_PARAMS: frozenset[str] = frozenset({
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "gclid",
    "fbclid",
    "msclkid",
    "mc_eid",
    "_hsenc",
    "_hsmi",
    "ref",
    "referrer",
    "source",
})


def normalize_url_identity(raw_url: str) -> str:
    """Normalize a user-provided URL into a canonical, deterministic identity representation.

    1. Trims leading/trailing whitespace.
    2. Lowercases scheme and hostname.
    3. Strips URL fragments (#...).
    4. Strips standard marketing and tracking query parameters (utm_*, gclid, fbclid, etc.).
    5. Normalizes dot segments in URL path while preserving trailing slash semantics.
    6. Strips default port numbers (:80 for HTTP, :443 for HTTPS).
    7. Sorts remaining query parameters deterministically.
    """
    import posixpath

    cleaned = raw_url.strip()
    if not cleaned:
        raise SSRFSecurityException(
            error_code="SSRF_INVALID_URL",
            message="URL cannot be empty or whitespace.",
        )

    parsed = urllib.parse.urlsplit(cleaned)
    if not parsed.scheme or not parsed.netloc:
        raise SSRFSecurityException(
            error_code="SSRF_INVALID_URL",
            message=f"URL '{raw_url}' is missing scheme or hostname.",
            detail={"url": raw_url},
        )

    scheme = parsed.scheme.lower()

    if "@" in parsed.netloc:
        raise SSRFSecurityException(
            error_code="SSRF_USERINFO_FORBIDDEN",
            message="Userinfo in URL is forbidden.",
            detail={"url": raw_url},
        )

    host = parsed.hostname.lower() if parsed.hostname else ""
    port = parsed.port

    # Strip standard default ports
    if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
        port = None

    netloc_clean = f"{host}:{port}" if port else host

    # Normalize dot segments
    raw_path = parsed.path or "/"
    ends_with_slash = raw_path.endswith("/") and raw_path != "/"
    normalized_path = posixpath.normpath(raw_path)
    if not normalized_path.startswith("/"):
        normalized_path = "/" + normalized_path
    if ends_with_slash and not normalized_path.endswith("/"):
        normalized_path += "/"

    # Query parameter filtering & deterministic sorting
    query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered_query = [
        (k, v) for k, v in query_items
        if k.lower() not in STANDARD_TRACKING_QUERY_PARAMS
    ]
    filtered_query.sort(key=lambda x: (x[0], x[1]))
    clean_query = urllib.parse.urlencode(filtered_query)

    return urllib.parse.urlunsplit((scheme, netloc_clean, normalized_path, clean_query, ""))

