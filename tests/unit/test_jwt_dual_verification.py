"""Unit tests for AUD-009: Dual-Verification JWT Architecture & Startup Validation."""

from datetime import UTC, datetime, timedelta
import os
import time
from unittest.mock import AsyncMock, patch
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import jwt
import pytest

from backend.core.exceptions.auth import ExpiredTokenException, InvalidTokenException
from backend.core.security.jwt import JWTService
from backend.core.startup_validator import StartupValidator


@pytest.fixture(scope="module")
def rsa_key_pair():
    """Generate ephemeral RSA key pair for testing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


@pytest.fixture
def hmac_secret():
    return "a" * 32  # 32 bytes strong HMAC secret


def build_valid_claims(sub="user-123", iss="raguard-auth-server", aud="raguard-api", exp_offset=900, nbf_offset=0):
    now = int(time.time())
    return {
        "sub": sub,
        "iss": iss,
        "aud": aud,
        "exp": now + exp_offset,
        "iat": now,
        "nbf": now + nbf_offset,
        "jti": str(uuid.uuid4()),
        "role": "admin",
        "email": "admin@example.com",
        "workspace_id": str(uuid.uuid4()),
    }


@pytest.mark.asyncio
async def test_valid_rs256_verification(rsa_key_pair, hmac_secret):
    priv_pem, pub_pem = rsa_key_pair
    service = JWTService(
        signing_algorithm="RS256",
        allowed_algorithms=["RS256", "HS256"],
        hmac_secret_key=hmac_secret,
        rsa_private_key=priv_pem,
        rsa_public_key=pub_pem,
    )
    service.redis = None

    claims = build_valid_claims()
    token = jwt.encode(claims, priv_pem, algorithm="RS256")

    payload = await service.verify_token(token)
    assert payload.sub == "user-123"
    assert payload.role == "admin"
    assert payload.email == "admin@example.com"


@pytest.mark.asyncio
async def test_valid_hs256_dual_verification(rsa_key_pair, hmac_secret):
    priv_pem, pub_pem = rsa_key_pair
    service = JWTService(
        signing_algorithm="RS256",
        allowed_algorithms=["RS256", "HS256"],
        hmac_secret_key=hmac_secret,
        rsa_private_key=priv_pem,
        rsa_public_key=pub_pem,
    )
    service.redis = None

    claims = build_valid_claims()
    token = jwt.encode(claims, hmac_secret, algorithm="HS256")

    payload = await service.verify_token(token)
    assert payload.sub == "user-123"
    assert payload.role == "admin"


@pytest.mark.asyncio
async def test_algorithm_confusion_prevention(rsa_key_pair, hmac_secret):
    import base64
    import hashlib
    import hmac
    import json

    priv_pem, pub_pem = rsa_key_pair
    service = JWTService(
        signing_algorithm="RS256",
        allowed_algorithms=["RS256", "HS256"],
        hmac_secret_key=hmac_secret,
        rsa_private_key=priv_pem,
        rsa_public_key=pub_pem,
    )
    service.redis = None

    # Craft token whose header says HS256, but signature is computed using the public key as HMAC secret
    claims = build_valid_claims()
    header = {"alg": "HS256", "typ": "JWT"}
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    msg = f"{h_b64}.{p_b64}".encode()
    sig = base64.urlsafe_b64encode(hmac.new(pub_pem.encode(), msg, hashlib.sha256).digest()).decode().rstrip("=")
    malicious_token = f"{h_b64}.{p_b64}.{sig}"

    # Verifier selects self.hmac_secret_key (not pub_pem) for HS256, rejecting the forgery
    with pytest.raises(InvalidTokenException):
        await service.verify_token(malicious_token)


@pytest.mark.asyncio
async def test_algorithm_header_mismatch_rejection(rsa_key_pair, hmac_secret):
    priv_pem, pub_pem = rsa_key_pair
    service = JWTService(
        signing_algorithm="RS256",
        allowed_algorithms=["RS256"],  # Only RS256 allowed
        hmac_secret_key=hmac_secret,
        rsa_private_key=priv_pem,
        rsa_public_key=pub_pem,
    )
    service.redis = None

    claims = build_valid_claims()
    hs_token = jwt.encode(claims, hmac_secret, algorithm="HS256")

    with pytest.raises(InvalidTokenException) as exc_info:
        await service.verify_token(hs_token)
    assert "Unauthorized token algorithm" in str(exc_info.value)


@pytest.mark.asyncio
async def test_algorithm_none_rejected(rsa_key_pair, hmac_secret):
    priv_pem, pub_pem = rsa_key_pair
    service = JWTService(
        signing_algorithm="RS256",
        allowed_algorithms=["RS256", "HS256"],
        hmac_secret_key=hmac_secret,
        rsa_private_key=priv_pem,
        rsa_public_key=pub_pem,
    )
    service.redis = None

    claims = build_valid_claims()
    none_token = jwt.encode(claims, key="", algorithm="none")

    with pytest.raises(InvalidTokenException):
        await service.verify_token(none_token)


@pytest.mark.asyncio
async def test_expired_token_raises_expired_token_exception(rsa_key_pair, hmac_secret):
    priv_pem, pub_pem = rsa_key_pair
    service = JWTService(
        signing_algorithm="RS256",
        allowed_algorithms=["RS256", "HS256"],
        hmac_secret_key=hmac_secret,
        rsa_private_key=priv_pem,
        rsa_public_key=pub_pem,
    )
    service.redis = None

    claims = build_valid_claims(exp_offset=-100)
    token = jwt.encode(claims, hmac_secret, algorithm="HS256")

    with pytest.raises(ExpiredTokenException):
        await service.verify_token(token)


@pytest.mark.asyncio
async def test_immature_token_before_nbf_rejected(rsa_key_pair, hmac_secret):
    priv_pem, pub_pem = rsa_key_pair
    service = JWTService(
        signing_algorithm="RS256",
        allowed_algorithms=["RS256", "HS256"],
        hmac_secret_key=hmac_secret,
        rsa_private_key=priv_pem,
        rsa_public_key=pub_pem,
    )
    service.redis = None

    claims = build_valid_claims(nbf_offset=300)  # nbf in 5 minutes
    token = jwt.encode(claims, hmac_secret, algorithm="HS256")

    with pytest.raises(InvalidTokenException):
        await service.verify_token(token)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_claim", ["exp", "iss", "aud", "sub", "jti", "nbf"])
async def test_missing_required_claims_rejected(rsa_key_pair, hmac_secret, missing_claim):
    priv_pem, pub_pem = rsa_key_pair
    service = JWTService(
        signing_algorithm="RS256",
        allowed_algorithms=["RS256", "HS256"],
        hmac_secret_key=hmac_secret,
        rsa_private_key=priv_pem,
        rsa_public_key=pub_pem,
    )
    service.redis = None

    claims = build_valid_claims()
    del claims[missing_claim]
    token = jwt.encode(claims, hmac_secret, algorithm="HS256")

    with pytest.raises(InvalidTokenException):
        await service.verify_token(token)


@pytest.mark.asyncio
async def test_issuer_mismatch_rejected(rsa_key_pair, hmac_secret):
    priv_pem, pub_pem = rsa_key_pair
    service = JWTService(
        signing_algorithm="RS256",
        allowed_algorithms=["RS256", "HS256"],
        hmac_secret_key=hmac_secret,
        rsa_private_key=priv_pem,
        rsa_public_key=pub_pem,
    )
    service.redis = None

    claims = build_valid_claims(iss="wrong-issuer")
    token = jwt.encode(claims, hmac_secret, algorithm="HS256")

    with pytest.raises(InvalidTokenException):
        await service.verify_token(token)


@pytest.mark.asyncio
async def test_audience_mismatch_rejected(rsa_key_pair, hmac_secret):
    priv_pem, pub_pem = rsa_key_pair
    service = JWTService(
        signing_algorithm="RS256",
        allowed_algorithms=["RS256", "HS256"],
        hmac_secret_key=hmac_secret,
        rsa_private_key=priv_pem,
        rsa_public_key=pub_pem,
    )
    service.redis = None

    claims = build_valid_claims(aud="wrong-audience")
    token = jwt.encode(claims, hmac_secret, algorithm="HS256")

    with pytest.raises(InvalidTokenException):
        await service.verify_token(token)


def test_startup_validator_rejects_fallback_secret_in_production(monkeypatch):
    from backend.core.config import get_settings
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "fallback-secret-key-do-not-use-in-production")
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    get_settings.cache_clear()
    try:
        validator = StartupValidator()
        with pytest.raises(ValueError) as exc_info:
            validator._validate_jwt_security()
        assert "Rejecting hardcoded fallback JWT secret" in str(exc_info.value)
    finally:
        get_settings.cache_clear()


def test_startup_validator_rejects_short_secret_in_production(monkeypatch):
    from backend.core.config import get_settings
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "too-short")
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    get_settings.cache_clear()
    try:
        validator = StartupValidator()
        with pytest.raises(ValueError) as exc_info:
            validator._validate_jwt_security()
        assert "must be at least 32 bytes" in str(exc_info.value)
    finally:
        get_settings.cache_clear()


def test_startup_validator_passes_strong_secret_in_production(monkeypatch):
    from backend.core.config import get_settings
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "s" * 32)
    get_settings.cache_clear()
    try:
        validator = StartupValidator()
        # Should not raise
        validator._validate_jwt_security()
    finally:
        get_settings.cache_clear()
