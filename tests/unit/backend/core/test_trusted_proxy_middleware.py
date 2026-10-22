"""Unit tests for TrustedProxyMiddleware."""

import ipaddress
import socket
from unittest.mock import patch
import pytest
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from backend.core.config.security import SecuritySettings
from backend.core.middleware.proxy import TrustedProxyMiddleware


@pytest.fixture
def trusted_networks():
    return [
        ipaddress.ip_network("127.0.0.1/32"),
        ipaddress.ip_network("::1/128"),
        ipaddress.ip_network("172.18.0.2/32"),  # Exact frontend container IP
    ]


@pytest.fixture
def middleware(trusted_networks):
    async def dummy_app(scope, receive, send):
        pass

    return TrustedProxyMiddleware(dummy_app, trusted_proxies=trusted_networks)


def create_request(client_host: str, headers: dict[str, str] | None = None) -> Request:
    raw_headers = []
    if headers:
        for k, v in headers.items():
            raw_headers.append((k.lower().encode("latin-1"), v.encode("latin-1")))

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": raw_headers,
        "client": (client_host, 12345),
    }
    return Request(scope)


def test_direct_untrusted_request_ignores_spoofed_x_forwarded_for(middleware):
    """Untrusted client sending spoofed X-Forwarded-For must be ignored."""
    req = create_request(
        client_host="203.0.113.50",
        headers={"X-Forwarded-For": "1.1.1.1, 8.8.8.8"},
    )
    resolved_ip = middleware.resolve_client_ip(req)
    assert resolved_ip == "203.0.113.50"


def test_direct_untrusted_request_ignores_spoofed_x_real_ip(middleware):
    """Untrusted client sending spoofed X-Real-IP must be ignored."""
    req = create_request(
        client_host="203.0.113.50",
        headers={"X-Real-IP": "10.0.0.1"},
    )
    resolved_ip = middleware.resolve_client_ip(req)
    assert resolved_ip == "203.0.113.50"


def test_untrusted_internal_container_cannot_spoof_headers(middleware):
    """Worker container (172.18.0.3) on same bridge subnet is not trusted; spoofed XFF ignored."""
    req = create_request(
        client_host="172.18.0.3",
        headers={"X-Forwarded-For": "203.0.113.195"},
    )
    resolved_ip = middleware.resolve_client_ip(req)
    assert resolved_ip == "172.18.0.3"


def test_trusted_proxy_single_hop(middleware):
    """Request arriving from trusted proxy resolves true client IP from X-Forwarded-For."""
    req = create_request(
        client_host="172.18.0.2",
        headers={"X-Forwarded-For": "198.51.100.25"},
    )
    resolved_ip = middleware.resolve_client_ip(req)
    assert resolved_ip == "198.51.100.25"


def test_trusted_proxy_multi_hop_strips_internal_proxies(middleware):
    """Multi-hop proxy chain strips intermediate trusted proxies right-to-left."""
    req = create_request(
        client_host="172.18.0.2",
        headers={"X-Forwarded-For": "203.0.113.99, 127.0.0.1"},
    )
    resolved_ip = middleware.resolve_client_ip(req)
    assert resolved_ip == "203.0.113.99"


def test_trusted_proxy_with_malformed_header(middleware):
    """Malformed tokens in X-Forwarded-For are skipped safely."""
    req = create_request(
        client_host="172.18.0.2",
        headers={"X-Forwarded-For": "bad-ip-string, 198.51.100.42"},
    )
    resolved_ip = middleware.resolve_client_ip(req)
    assert resolved_ip == "198.51.100.42"


def test_trusted_proxy_all_malformed_falls_back_to_host(middleware):
    """If all tokens in X-Forwarded-For are invalid, fall back to peer host."""
    req = create_request(
        client_host="172.18.0.2",
        headers={"X-Forwarded-For": "not-an-ip, completely-invalid"},
    )
    resolved_ip = middleware.resolve_client_ip(req)
    assert resolved_ip == "172.18.0.2"


def test_trusted_proxy_x_real_ip_fallback(middleware):
    """If X-Forwarded-For is missing, inspect X-Real-IP."""
    req = create_request(
        client_host="172.18.0.2",
        headers={"X-Real-IP": "198.51.100.77"},
    )
    resolved_ip = middleware.resolve_client_ip(req)
    assert resolved_ip == "198.51.100.77"


def test_trusted_proxy_no_headers_falls_back_to_host(middleware):
    """Trusted proxy connection with no forwarding headers resolves to the proxy IP itself."""
    req = create_request(client_host="172.18.0.2")
    resolved_ip = middleware.resolve_client_ip(req)
    assert resolved_ip == "172.18.0.2"


@pytest.mark.asyncio
async def test_dispatch_sets_request_state(middleware):
    """Middleware dispatch attaches resolved client IP to request.state.client_ip."""
    req = create_request(
        client_host="172.18.0.2",
        headers={"X-Forwarded-For": "198.51.100.88"},
    )

    captured_ip = None

    async def call_next(request: Request):
        nonlocal captured_ip
        captured_ip = getattr(request.state, "client_ip", None)
        return PlainTextResponse("ok")

    response = await middleware.dispatch(req, call_next)
    assert response.status_code == 200
    assert captured_ip == "198.51.100.88"


# Configuration and DNS Resolution Tests

def test_security_settings_resolves_hostname():
    """SecuritySettings resolves hostnames like 'frontend' to IP networks."""
    with patch("socket.gethostbyname_ex", return_value=("frontend", [], ["172.18.0.2"])):
        settings = SecuritySettings(TRUSTED_PROXIES="127.0.0.1,::1,frontend")
        networks = settings.trusted_proxy_networks
        assert ipaddress.ip_network("127.0.0.1/32") in networks
        assert ipaddress.ip_network("::1/128") in networks
        assert ipaddress.ip_network("172.18.0.2/32") in networks


def test_security_settings_unresolvable_hostname_falls_back_safely():
    """Unresolvable hostnames log warning and fall back safely to valid/loopback networks."""
    with patch("socket.gethostbyname_ex", side_effect=socket.gaierror("Name or service not known")):
        settings = SecuritySettings(TRUSTED_PROXIES="127.0.0.1,unresolvable-proxy-host")
        networks = settings.trusted_proxy_networks
        assert ipaddress.ip_network("127.0.0.1/32") in networks
        assert len(networks) == 1


def test_security_settings_empty_config_falls_back_to_loopback():
    """Empty or whitespace TRUSTED_PROXIES defaults safely to loopback."""
    settings = SecuritySettings(TRUSTED_PROXIES="")
    networks = settings.trusted_proxy_networks
    assert ipaddress.ip_network("127.0.0.1/32") in networks
    assert ipaddress.ip_network("::1/128") in networks


def test_security_settings_malformed_cidr_falls_back_safely():
    """Malformed CIDR or IP entries are skipped safely."""
    settings = SecuritySettings(TRUSTED_PROXIES="999.999.999.999/99,127.0.0.1")
    networks = settings.trusted_proxy_networks
    assert ipaddress.ip_network("127.0.0.1/32") in networks
    assert len(networks) == 1


def test_middleware_ttl_caching():
    """Middleware caches resolved networks within TTL."""
    async def dummy_app(scope, receive, send):
        pass

    with patch("socket.gethostbyname_ex", return_value=("frontend", [], ["172.18.0.2"])) as mock_dns:
        mw = TrustedProxyMiddleware(dummy_app, cache_ttl_seconds=60.0)
        req = create_request(client_host="172.18.0.2", headers={"X-Forwarded-For": "1.2.3.4"})
        
        # Call 1: triggers resolution
        ip1 = mw.resolve_client_ip(req)
        assert ip1 == "1.2.3.4"
        assert mock_dns.call_count == 1
        
        # Call 2: within TTL, uses cached networks
        ip2 = mw.resolve_client_ip(req)
        assert ip2 == "1.2.3.4"
        assert mock_dns.call_count == 1
