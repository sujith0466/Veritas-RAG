"""Unit tests for enterprise SSRF Safe URL Validator, Comprehensive CIDR Blacklist,
and Pin-to-IP Transport.
"""

from __future__ import annotations

import ipaddress
import ssl
from unittest.mock import AsyncMock, patch

import httpcore
from httpcore._backends.auto import AutoBackend
import httpx
import pytest

from backend.document.services.url_security import (
    PinToIPBackend,
    PinToIPTransport,
    SSRFSafeUrlValidator,
    SSRFSecurityException,
    ValidatedDestinationDTO,
    create_ssrf_safe_client,
    validate_redirect_destination,
)


class TestSSRFUrlSyntaxValidation:
    """Tests for URL syntax, scheme, userinfo, and port restrictions."""

    def test_valid_https_url(self) -> None:
        scheme, host, port, path_and_query = SSRFSafeUrlValidator.validate_url_syntax(
            "https://example.com/docs?query=rag"
        )
        assert scheme == "https"
        assert host == "example.com"
        assert port == 443
        assert path_and_query == "/docs?query=rag"

    def test_valid_http_url(self) -> None:
        scheme, host, port, path_and_query = SSRFSafeUrlValidator.validate_url_syntax(
            "http://example.com:80/index.html"
        )
        assert scheme == "http"
        assert host == "example.com"
        assert port == 80
        assert path_and_query == "/index.html"

    def test_empty_or_whitespace_url_rejected(self) -> None:
        with pytest.raises(SSRFSecurityException) as exc:
            SSRFSafeUrlValidator.validate_url_syntax("   ")
        assert exc.value.error_code == "SSRF_INVALID_URL"

    def test_oversized_url_rejected(self) -> None:
        oversized = "https://example.com/" + ("a" * 2050)
        with pytest.raises(SSRFSecurityException) as exc:
            SSRFSafeUrlValidator.validate_url_syntax(oversized)
        assert exc.value.error_code == "SSRF_INVALID_URL"

    @pytest.mark.parametrize(
        "forbidden_scheme",
        [
            "file:///etc/passwd",
            "gopher://127.0.0.1:6379/_FLUSHALL",
            "ftp://example.com/file.txt",
            "ldap://127.0.0.1:389/o=example",
            "dict://127.0.0.1:11211/stat",
            "javascript:alert(1)",
            "data:text/html,<h1>Hello</h1>",
        ],
    )
    def test_forbidden_schemes_rejected(self, forbidden_scheme: str) -> None:
        with pytest.raises(SSRFSecurityException) as exc:
            SSRFSafeUrlValidator.validate_url_syntax(forbidden_scheme)
        assert exc.value.error_code == "SSRF_FORBIDDEN_SCHEME"

    @pytest.mark.parametrize(
        "userinfo_url",
        [
            "https://admin:password@example.com/docs",
            "http://user@example.com/secret",
            "https://root:toor@93.184.216.34/",
        ],
    )
    def test_userinfo_credentials_rejected(self, userinfo_url: str) -> None:
        with pytest.raises(SSRFSecurityException) as exc:
            SSRFSafeUrlValidator.validate_url_syntax(userinfo_url)
        assert exc.value.error_code == "SSRF_USERINFO_NOT_ALLOWED"

    @pytest.mark.parametrize(
        "forbidden_port_url",
        [
            "http://example.com:22/ssh",
            "http://example.com:25/smtp",
            "http://example.com:5432/postgres",
            "http://example.com:6379/redis",
            "http://example.com:6333/qdrant",
            "http://example.com:8000/fastapi",
            "http://example.com:8080/proxy",
            "http://example.com:9090/prometheus",
        ],
    )
    def test_forbidden_ports_rejected(self, forbidden_port_url: str) -> None:
        with pytest.raises(SSRFSecurityException) as exc:
            SSRFSafeUrlValidator.validate_url_syntax(forbidden_port_url)
        assert exc.value.error_code == "SSRF_FORBIDDEN_PORT"


class TestSSRFIPBlacklistEnforcement:
    """Tests for comprehensive IP range and CIDR blacklist checks."""

    @pytest.mark.parametrize(
        "ip_str",
        [
            # Loopback
            "127.0.0.1",
            "127.0.1.1",
            "127.255.255.255",
            "::1",
            # Unspecified
            "0.0.0.0",
            "::",
            # RFC 1918 Private
            "10.0.0.1",
            "10.255.255.254",
            "172.16.0.1",
            "172.31.255.254",
            "192.168.0.1",
            "192.168.254.254",
            # Link-Local & Cloud Metadata / IMDS
            "169.254.169.254",
            "169.254.1.1",
            "fe80::1",
            "fd00:ec2::254",
            # Shared Address Space / CGNAT (Alibaba Metadata 100.100.100.200)
            "100.64.0.1",
            "100.100.100.200",
            "100.127.255.254",
            # IPv6 ULA
            "fc00::1",
            "fd12:3456:789a::1",
            # Multicast
            "224.0.0.1",
            "ff02::1",
            # Reserved / Broadcast
            "240.0.0.1",
            "255.255.255.255",
            # Documentation
            "192.0.2.1",
            "198.51.100.1",
            "203.0.113.1",
            "2001:db8::1",
        ],
    )
    def test_forbidden_ip_ranges_detected(self, ip_str: str) -> None:
        ip = ipaddress.ip_address(ip_str)
        is_forbidden, reason = SSRFSafeUrlValidator.is_ip_forbidden(ip)
        assert is_forbidden is True
        assert isinstance(reason, str)
        assert len(reason) > 0

    @pytest.mark.parametrize(
        "public_ip",
        [
            "93.184.216.34",  # example.com
            "8.8.8.8",        # Google DNS
            "1.1.1.1",        # Cloudflare DNS
            "2606:2800:220:1:248:1893:25c8:1946",  # example.com IPv6
        ],
    )
    def test_allowed_public_ips(self, public_ip: str) -> None:
        ip = ipaddress.ip_address(public_ip)
        is_forbidden, reason = SSRFSafeUrlValidator.is_ip_forbidden(ip)
        assert is_forbidden is False
        assert reason == "Allowed Public Address"

    @pytest.mark.parametrize(
        ("mapped_ipv6", "expected_unpacked"),
        [
            ("::ffff:127.0.0.1", "127.0.0.1"),
            ("::ffff:10.0.0.1", "10.0.0.1"),
            ("::ffff:169.254.169.254", "169.254.169.254"),
            ("::ffff:93.184.216.34", "93.184.216.34"),
            ("64:ff9b::127.0.0.1", "127.0.0.1"),
        ],
    )
    def test_ipv4_mapped_ipv6_unpacking(self, mapped_ipv6: str, expected_unpacked: str) -> None:
        ip = ipaddress.ip_address(mapped_ipv6)
        unpacked = SSRFSafeUrlValidator.unpack_and_normalize_ip(ip)
        assert str(unpacked) == expected_unpacked

    def test_ipv4_mapped_ipv6_loopback_blocked(self) -> None:
        ip = ipaddress.ip_address("::ffff:127.0.0.1")
        is_forbidden, _ = SSRFSafeUrlValidator.is_ip_forbidden(ip)
        assert is_forbidden is True

    def test_ipv4_mapped_ipv6_cloud_metadata_blocked(self) -> None:
        ip = ipaddress.ip_address("::ffff:169.254.169.254")
        is_forbidden, _ = SSRFSafeUrlValidator.is_ip_forbidden(ip)
        assert is_forbidden is True


class TestSSRFDNSResolutionAndValidation:
    """Tests for multi-record DNS resolution and comprehensive IP rejection."""

    @pytest.mark.asyncio
    async def test_literal_ip_url_validation_success(self) -> None:
        dest = await SSRFSafeUrlValidator.validate_destination("https://93.184.216.34/docs")
        assert dest.scheme == "https"
        assert dest.host == "93.184.216.34"
        assert dest.port == 443
        assert dest.pinned_ip == "93.184.216.34"
        assert "93.184.216.34" in dest.resolved_ips

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "literal_blocked_url",
        [
            "http://127.0.0.1:80/admin",
            "https://127.0.0.1/admin",
            "http://10.0.0.1/private",
            "https://169.254.169.254/latest/meta-data",
            "http://[::1]/internal",
            "http://[::ffff:127.0.0.1]/",
        ],
    )
    async def test_literal_blocked_ip_url_rejected(self, literal_blocked_url: str) -> None:
        with pytest.raises(SSRFSecurityException) as exc:
            await SSRFSafeUrlValidator.validate_destination(literal_blocked_url)
        assert exc.value.error_code == "SSRF_IP_BLOCKED"

    @pytest.mark.asyncio
    async def test_domain_resolving_to_multiple_safe_ips(self) -> None:
        mock_ips = [
            ipaddress.IPv4Address("93.184.216.34"),
            ipaddress.IPv4Address("93.184.216.35"),
        ]
        with patch.object(SSRFSafeUrlValidator, "resolve_all_ips", AsyncMock(return_value=mock_ips)):
            dest = await SSRFSafeUrlValidator.validate_destination("https://example.com/test")
            assert dest.pinned_ip == "93.184.216.34"
            assert len(dest.resolved_ips) == 2

    @pytest.mark.asyncio
    async def test_domain_resolving_to_mixed_safe_and_private_ips_rejected(self) -> None:
        # Rebinding / split-horizon attack simulation: domain has public A and private A
        mock_ips = [
            ipaddress.IPv4Address("93.184.216.34"),
            ipaddress.IPv4Address("127.0.0.1"),  # Malicious second record
        ]
        with patch.object(SSRFSafeUrlValidator, "resolve_all_ips", AsyncMock(return_value=mock_ips)):
            with pytest.raises(SSRFSecurityException) as exc:
                await SSRFSafeUrlValidator.validate_destination("https://rebind.attacker.com/data")
            assert exc.value.error_code == "SSRF_IP_BLOCKED"
            assert "127.0.0.1" in str(exc.value)

    @pytest.mark.asyncio
    async def test_domain_with_public_a_and_private_aaaa_rejected(self) -> None:
        mock_ips = [
            ipaddress.IPv4Address("93.184.216.34"),
            ipaddress.IPv6Address("::1"),  # IPv6 loopback
        ]
        with patch.object(SSRFSafeUrlValidator, "resolve_all_ips", AsyncMock(return_value=mock_ips)):
            with pytest.raises(SSRFSecurityException) as exc:
                await SSRFSafeUrlValidator.validate_destination("https://dual-stack.attacker.com/")
            assert exc.value.error_code == "SSRF_IP_BLOCKED"

    @pytest.mark.asyncio
    async def test_dns_resolution_failure_raises_exception(self) -> None:
        with patch.object(SSRFSafeUrlValidator, "resolve_all_ips", AsyncMock(return_value=[])):
            with pytest.raises(SSRFSecurityException) as exc:
                await SSRFSafeUrlValidator.validate_destination("https://unresolvable-domain-xyz.local/")
            assert exc.value.error_code == "SSRF_DNS_RESOLUTION_FAILED"


class TestPinToIPTransportMechanics:
    """Tests for Pin-to-IP socket binding and connection backend override."""

    @pytest.mark.asyncio
    async def test_pin_to_ip_backend_overrides_connect_tcp_target(self) -> None:
        backend = PinToIPBackend(pinned_ip="93.184.216.34")
        assert backend.pinned_ip == "93.184.216.34"

        # Mock super().connect_tcp to verify it receives pinned_ip instead of host
        with patch.object(AutoBackend, "connect_tcp", AsyncMock(return_value="mock_stream")) as mock_connect:
            stream = await backend.connect_tcp(host="example.com", port=443, timeout=5.0)
            assert stream == "mock_stream"
            # Crucial verification: connect_tcp was called with '93.184.216.34', NOT 'example.com'!
            mock_connect.assert_called_once_with(
                "93.184.216.34",
                443,
                timeout=5.0,
                local_address=None,
                socket_options=None,
            )

    def test_create_ssrf_safe_client_config(self) -> None:
        destination = ValidatedDestinationDTO(
            url="https://example.com/docs",
            scheme="https",
            host="example.com",
            port=443,
            path_and_query="/docs",
            resolved_ips=["93.184.216.34"],
            pinned_ip="93.184.216.34",
        )
        client = create_ssrf_safe_client(destination)
        assert isinstance(client._transport, PinToIPTransport)
        assert client._transport.pinned_ip == "93.184.216.34"


class TestRedirectValidation:
    """Tests for per-hop redirect validation and downgrade prevention."""

    @pytest.fixture
    def current_dest(self) -> ValidatedDestinationDTO:
        return ValidatedDestinationDTO(
            url="https://example.com/source",
            scheme="https",
            host="example.com",
            port=443,
            path_and_query="/source",
            resolved_ips=["93.184.216.34"],
            pinned_ip="93.184.216.34",
        )

    @pytest.mark.asyncio
    async def test_valid_relative_redirect(self, current_dest: ValidatedDestinationDTO) -> None:
        mock_ips = [ipaddress.IPv4Address("93.184.216.34")]
        with patch.object(SSRFSafeUrlValidator, "resolve_all_ips", AsyncMock(return_value=mock_ips)):
            new_dest = await validate_redirect_destination(
                current_destination=current_dest,
                redirect_location="/docs/v2",
                hop_count=1,
            )
            assert new_dest.url == "https://example.com/docs/v2"
            assert new_dest.pinned_ip == "93.184.216.34"

    @pytest.mark.asyncio
    async def test_redirect_to_private_ip_blocked(self, current_dest: ValidatedDestinationDTO) -> None:
        # Attacker redirects from public https://example.com to http://169.254.169.254/
        with pytest.raises(SSRFSecurityException) as exc:
            await validate_redirect_destination(
                current_destination=current_dest,
                redirect_location="https://169.254.169.254/latest/meta-data",
                hop_count=1,
            )
        assert exc.value.error_code == "SSRF_IP_BLOCKED"

    @pytest.mark.asyncio
    async def test_https_to_http_downgrade_blocked(self, current_dest: ValidatedDestinationDTO) -> None:
        with pytest.raises(SSRFSecurityException) as exc:
            await validate_redirect_destination(
                current_destination=current_dest,
                redirect_location="http://example.com/insecure",
                hop_count=1,
                allow_http_downgrade=False,
            )
        assert exc.value.error_code == "SSRF_REDIRECT_FORBIDDEN"
        assert "downgrade" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_exceeded_hop_limit_blocked(self, current_dest: ValidatedDestinationDTO) -> None:
        with pytest.raises(SSRFSecurityException) as exc:
            await validate_redirect_destination(
                current_destination=current_dest,
                redirect_location="https://example.com/next",
                hop_count=3,
                max_hops=3,
            )
        assert exc.value.error_code == "SSRF_REDIRECT_FORBIDDEN"
        assert "maximum allowed redirect hops" in str(exc.value)


class TestD41SecurityEvidenceGate:
    """Rigorous runtime evidence verification for D4.1 security guarantees."""

    @pytest.mark.asyncio
    async def test_evidence_tcp_connection_destination_pinning(self) -> None:
        """Evidence B: PinToIPTransport directly connects to target IP X and NOT domain name."""
        pinned_ip = "93.184.216.34"
        transport = PinToIPTransport(pinned_ip=pinned_ip)

        with patch.object(AutoBackend, "connect_tcp", AsyncMock(return_value="mock_stream")) as mock_connect:
            # Execute transport connection directly via backend
            stream = await transport.backend.connect_tcp(host="example.com", port=443, timeout=5.0)
            assert stream == "mock_stream"
            # Proven: The physical TCP connection was made to '93.184.216.34', NOT 'example.com'
            mock_connect.assert_called_once_with(
                pinned_ip,
                443,
                timeout=5.0,
                local_address=None,
                socket_options=None,
            )

    @pytest.mark.asyncio
    async def test_evidence_http_host_header_preservation(self) -> None:
        """Evidence C: HTTP Host header remains the original domain name."""
        pinned_ip = "93.184.216.34"
        transport = PinToIPTransport(pinned_ip=pinned_ip)

        request = httpx.Request("GET", "https://example.com/api/v1/resource")
        assert request.headers["host"] == "example.com"

        # Mock pool handle_async_request to inspect the dispatched httpcore.Request
        mock_response = httpcore.Response(status=200, headers=[], content=b"ok")
        with patch.object(transport._pool, "handle_async_request", AsyncMock(return_value=mock_response)) as mock_handle:
            resp = await transport.handle_async_request(request)
            assert resp.status_code == 200

            # Proven: Dispatched request preserved original host and headers
            dispatched_req: httpcore.Request = mock_handle.call_args[0][0]
            assert dispatched_req.url.host == b"example.com"
            assert dispatched_req.url.target == b"/api/v1/resource"
            headers_dict = {k.lower(): v for k, v in dispatched_req.headers}
            assert headers_dict.get(b"host") == b"example.com"

    def test_evidence_tls_certificate_verification_enabled(self) -> None:
        """Evidence D & E: TLS SNI and Certificate Verification remain strictly enabled."""
        pinned_ip = "93.184.216.34"
        transport = PinToIPTransport(pinned_ip=pinned_ip, verify=True)

        ssl_ctx = transport._pool._ssl_context
        assert isinstance(ssl_ctx, ssl.SSLContext)
        # Proven: Certificate verification is enforced (CERT_REQUIRED) and check_hostname is True
        assert ssl_ctx.verify_mode == ssl.CERT_REQUIRED
        assert ssl_ctx.check_hostname is True

    @pytest.mark.asyncio
    async def test_evidence_dns_rebinding_second_resolution_immunity(self) -> None:
        """Evidence F: Second-resolution / DNS rebinding cannot alter the pinned socket destination."""
        # 1. Pre-validation resolves to public IP
        initial_safe_ips = [ipaddress.IPv4Address("93.184.216.34")]
        with patch.object(SSRFSafeUrlValidator, "resolve_all_ips", AsyncMock(return_value=initial_safe_ips)):
            destination = await SSRFSafeUrlValidator.validate_destination("https://attacker-rebind.com/data")
            assert destination.pinned_ip == "93.184.216.34"

        # 2. Instantiate client with destination
        client = create_ssrf_safe_client(destination)
        transport: PinToIPTransport = client._transport  # type: ignore[assignment]
        assert transport.pinned_ip == "93.184.216.34"

        # 3. Simulate attacker altering DNS to point to 127.0.0.1 immediately after validation
        rebound_malicious_ips = [ipaddress.IPv4Address("127.0.0.1")]
        with (
            patch.object(SSRFSafeUrlValidator, "resolve_all_ips", AsyncMock(return_value=rebound_malicious_ips)),
            patch.object(AutoBackend, "connect_tcp", AsyncMock(return_value="mock_stream")) as mock_connect,
        ):
            await transport.backend.connect_tcp(host="attacker-rebind.com", port=443, timeout=5.0)
            # Proven: Connection is made to 93.184.216.34, completely ignoring DNS rebinding
            mock_connect.assert_called_once_with(
                "93.184.216.34",
                443,
                timeout=5.0,
                local_address=None,
                socket_options=None,
            )

    @pytest.mark.asyncio
    async def test_evidence_forbidden_record_fails_closed_before_egress(self) -> None:
        """Evidence G: If any resolved A/AAAA record is forbidden, validation fails closed."""
        mixed_dns_records = [
            ipaddress.IPv4Address("93.184.216.34"),
            ipaddress.IPv4Address("169.254.169.254"),  # AWS Cloud Metadata record
        ]
        with patch.object(SSRFSafeUrlValidator, "resolve_all_ips", AsyncMock(return_value=mixed_dns_records)):
            with pytest.raises(SSRFSecurityException) as exc:
                await SSRFSafeUrlValidator.validate_destination("https://metadata-exploit.com/secret")
            assert exc.value.error_code == "SSRF_IP_BLOCKED"
            assert "169.254.169.254" in str(exc.value)

    def test_evidence_proxy_environment_isolation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Evidence H: Environment proxy variables (HTTP_PROXY, HTTPS_PROXY, ALL_PROXY) are ignored."""
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:8888")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:8888")
        monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:8888")

        destination = ValidatedDestinationDTO(
            url="https://example.com/docs",
            scheme="https",
            host="example.com",
            port=443,
            path_and_query="/docs",
            resolved_ips=["93.184.216.34"],
            pinned_ip="93.184.216.34",
        )
        client = create_ssrf_safe_client(destination)
        # Proven: trust_env is False, preventing ambient proxy hijacking
        assert client._trust_env is False
        transport: PinToIPTransport = client._transport  # type: ignore[assignment]
        assert getattr(transport._pool, "_proxy", None) is None
