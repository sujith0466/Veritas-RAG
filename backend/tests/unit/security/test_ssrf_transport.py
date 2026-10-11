"""Tests for SSRF Protected Transport and Connection-Time DNS Pinning."""

import ipaddress
import socket
import ssl
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
import httpcore
import httpx

from backend.core.security.ssrf_transport import (
    SSRFProtectedTransport,
    SSRFProtectedAsyncBackend,
    SSRFValidationError,
    is_safe_ip,
)


def test_is_safe_ip_public_ipv4():
    assert is_safe_ip(ipaddress.ip_address("8.8.8.8")) is True
    assert is_safe_ip(ipaddress.ip_address("93.184.216.34")) is True


def test_is_safe_ip_blocks_private_and_loopback():
    assert is_safe_ip(ipaddress.ip_address("127.0.0.1")) is False
    assert is_safe_ip(ipaddress.ip_address("10.0.0.1")) is False
    assert is_safe_ip(ipaddress.ip_address("172.16.0.5")) is False
    assert is_safe_ip(ipaddress.ip_address("192.168.1.1")) is False
    assert is_safe_ip(ipaddress.ip_address("::1")) is False
    assert is_safe_ip(ipaddress.ip_address("fc00::1")) is False
    assert is_safe_ip(ipaddress.ip_address("fe80::1")) is False


def test_is_safe_ip_blocks_cloud_metadata():
    assert is_safe_ip(ipaddress.ip_address("169.254.169.254")) is False


def test_is_safe_ip_ipv4_mapped_ipv6():
    # IPv4-mapped IPv6 wrapping loopback
    assert is_safe_ip(ipaddress.ip_address("::ffff:127.0.0.1")) is False
    # IPv4-mapped IPv6 wrapping cloud metadata
    assert is_safe_ip(ipaddress.ip_address("::ffff:169.254.169.254")) is False
    # IPv4-mapped IPv6 wrapping private range
    assert is_safe_ip(ipaddress.ip_address("::ffff:192.168.1.100")) is False
    # IPv4-mapped IPv6 wrapping public IP
    assert is_safe_ip(ipaddress.ip_address("::ffff:8.8.8.8")) is True


def test_is_safe_ip_nat64():
    # Well-known NAT64 prefix RFC 6052
    nat64_public = ipaddress.ip_address("64:ff9b::808:808")  # embedded 8.8.8.8
    assert is_safe_ip(nat64_public) is True

    nat64_private = ipaddress.ip_address("64:ff9b::7f00:1")  # embedded 127.0.0.1
    assert is_safe_ip(nat64_private) is False


@pytest.mark.asyncio
async def test_backend_connect_tcp_dns_rebinding_rejection():
    """Simulates DNS rebinding where connect_tcp resolves host to private IP at connection time."""
    mock_default = AsyncMock(spec=httpcore.AsyncNetworkBackend)
    backend = SSRFProtectedAsyncBackend(default_backend=mock_default)

    with patch("socket.getaddrinfo") as mock_dns:
        # Mock DNS returning 127.0.0.1
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ]

        with pytest.raises(SSRFValidationError, match="prohibited or private IP '127.0.0.1'"):
            await backend.connect_tcp("rebound-attacker.com", 443)

    # Ensure no connection was initiated to default backend
    mock_default.connect_tcp.assert_not_called()


@pytest.mark.asyncio
async def test_backend_connect_tcp_pins_valid_ip():
    """Verifies that connect_tcp resolves and pins the connection to the validated IP."""
    mock_default = AsyncMock(spec=httpcore.AsyncNetworkBackend)
    mock_stream = AsyncMock(spec=httpcore.AsyncNetworkStream)
    mock_default.connect_tcp.return_value = mock_stream
    backend = SSRFProtectedAsyncBackend(default_backend=mock_default)

    with patch("socket.getaddrinfo") as mock_dns:
        # Returns public IP 93.184.216.34
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ]

        stream = await backend.connect_tcp("example.com", 443)
        assert stream == mock_stream

    # Must be called with the pinned IP address as the host
    mock_default.connect_tcp.assert_called_once_with(
        host="93.184.216.34",
        port=443,
        timeout=None,
        local_address=None,
        socket_options=None,
    )


@pytest.mark.asyncio
async def test_backend_connect_tcp_rejects_mixed_dns_with_private_first():
    """If DNS answers contain any prohibited IP, connection is strictly refused."""
    mock_default = AsyncMock(spec=httpcore.AsyncNetworkBackend)
    backend = SSRFProtectedAsyncBackend(default_backend=mock_default)

    with patch("socket.getaddrinfo") as mock_dns:
        mock_dns.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        ]

        with pytest.raises(SSRFValidationError, match="prohibited or private IP '10.0.0.1'"):
            await backend.connect_tcp("mixed-answers.com", 443)


@pytest.mark.asyncio
async def test_ssrf_transport_sni_preservation():
    """Validates that TLS start_tls receives the original hostname for SNI verification."""
    captured_sni = []

    class MockStream(httpcore.AsyncNetworkStream):
        async def aclose(self): pass
        async def read(self, max_bytes, timeout=None): return b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
        async def write(self, buffer, timeout=None): pass
        async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
            captured_sni.append(server_hostname)
            return self
        def get_extra_info(self, info): return None

    class MockNetworkBackend(httpcore.AsyncNetworkBackend):
        async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            return MockStream()
        async def sleep(self, seconds): pass

    transport = SSRFProtectedTransport()
    # Inject our mock network backend into the pool
    transport._pool._network_backend = MockNetworkBackend()

    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.get("https://secure.example.com/webhook")
        assert response.status_code == 200

    # Verify that SNI was passed with original hostname, NOT the IP address
    assert captured_sni == ["secure.example.com"]
