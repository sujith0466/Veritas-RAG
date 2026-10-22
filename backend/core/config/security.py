"""Security configuration settings."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


import os

def get_default_cors() -> str:
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        return ""
    return "http://localhost:5173,http://localhost:3000"

class SecuritySettings(BaseSettings):
    """CORS, rate limiting, and application security configuration."""

    # CORS — comma-separated list of allowed origins
    cors_origins_str: str = Field(
        default_factory=get_default_cors,
        alias="CORS_ORIGINS",
    )
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")
    cors_allow_methods: list[str] = Field(default=["*"])
    cors_allow_headers: list[str] = Field(default=["*"])

    # Allowed hosts — comma-separated; empty string = allow all
    allowed_hosts_str: str = Field(default="", alias="ALLOWED_HOSTS")

    # Rate limiting
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")

    # Trusted Proxies (explicit comma-separated CIDRs, IPs, or hostnames)
    trusted_proxies_str: str = Field(
        default="127.0.0.1,::1,frontend",
        alias="TRUSTED_PROXIES",
    )

    # SSE Stream Concurrency Throttling
    max_concurrent_sse_streams: int = Field(
        default=50,
        alias="MAX_CONCURRENT_SSE_STREAMS",
    )

    # File uploads
    max_upload_size_bytes: int = Field(
        default=52_428_800, alias="MAX_UPLOAD_SIZE_BYTES"
    )  # 50MB

    # Cookie security policy (None = dynamic by ENVIRONMENT; True/False overrides)
    cookie_secure_override: bool | None = Field(default=None, alias="COOKIE_SECURE")

    # JWT Configuration
    jwt_signing_algorithm: str = Field(default="HS256", alias="JWT_SIGNING_ALGORITHM")
    jwt_allowed_verification_algorithms: str | list[str] = Field(
        default=["HS256"], alias="JWT_ALLOWED_VERIFICATION_ALGORITHMS"
    )
    jwt_secret_key: str | None = Field(default=None, alias="JWT_SECRET_KEY")
    jwt_private_key: str | None = Field(default=None, alias="JWT_PRIVATE_KEY")
    jwt_public_key: str | None = Field(default=None, alias="JWT_PUBLIC_KEY")

    model_config = {
        "populate_by_name": True,
        "env_file": (".env", ".env.local"),
        "extra": "ignore",
    }

    @field_validator("cors_origins_str")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        origins = [o.strip() for o in v.split(",") if o.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS must contain at least one origin")
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_str.split(",") if o.strip()]

    @property
    def allowed_hosts(self) -> list[str]:
        if not self.allowed_hosts_str:
            return []
        return [h.strip() for h in self.allowed_hosts_str.split(",") if h.strip()]

    @property
    def cookie_secure(self) -> bool:
        if self.cookie_secure_override is not None:
            return self.cookie_secure_override
        env = os.getenv("ENVIRONMENT", "development").lower()
        return env in ("production", "staging")

    @property
    def allowed_jwt_algorithms(self) -> list[str]:
        if isinstance(self.jwt_allowed_verification_algorithms, list):
            return self.jwt_allowed_verification_algorithms
        if isinstance(self.jwt_allowed_verification_algorithms, str):
            return [a.strip() for a in self.jwt_allowed_verification_algorithms.split(",") if a.strip()]
        return ["HS256"]

    @property
    def trusted_proxy_networks(self) -> list:
        """Parse trusted proxy entries (CIDRs, IPs, and hostnames).

        Hostnames (e.g. 'frontend') are resolved to IP addresses via DNS.
        Invalid or unresolvable entries are logged as warnings.
        If no valid networks are resolved, falls back safely to loopback only.
        """
        import ipaddress
        import socket
        import structlog

        log = structlog.get_logger(__name__)
        networks = []
        for raw in self.trusted_proxies_str.split(","):
            raw = raw.strip()
            if not raw:
                continue
            # 1. Direct IP network or IP address
            try:
                networks.append(ipaddress.ip_network(raw, strict=False))
                continue
            except ValueError:
                pass

            # 2. Hostname resolution
            try:
                _, _, ip_list = socket.gethostbyname_ex(raw)
                for ip in ip_list:
                    networks.append(ipaddress.ip_network(f"{ip}/32", strict=False))
            except (socket.gaierror, socket.herror, OSError) as e:
                log.warning("trusted_proxy_hostname_resolution_failed", hostname=raw, error=str(e))
            except Exception as e:
                log.warning("trusted_proxy_entry_invalid", entry=raw, error=str(e))

        if not networks:
            log.warning("trusted_proxies_empty_or_unresolved_falling_back_to_loopback")
            return [ipaddress.ip_network("127.0.0.1/32"), ipaddress.ip_network("::1/128")]

        return networks
