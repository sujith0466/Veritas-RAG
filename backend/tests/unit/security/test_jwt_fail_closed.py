"""Unit tests for SEC-001: JWT Service fail-closed initialization and secret handling."""
import pytest
from unittest.mock import MagicMock, patch

from backend.core.security.jwt import JWTService


def test_sec001_jwt_service_fails_closed_in_production_without_secret(monkeypatch):
    """Prove that JWTService fails closed (raises ValueError) in production if secret key is missing."""
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)

    with patch("backend.core.config.get_settings") as mock_settings:
        mock_settings.return_value.security.jwt_secret_key = None
        mock_settings.return_value.app.secret_key = None
        mock_settings.return_value.is_testing = False

        with pytest.raises(ValueError, match="HMAC secret key .* must be configured in non-test environments"):
            JWTService(signing_algorithm="HS256")


def test_sec001_jwt_service_rs256_fails_closed_in_production_without_keys(monkeypatch):
    """Prove that JWTService fails closed for RS256 in production if RSA keys are missing."""
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("JWT_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("JWT_PUBLIC_KEY", raising=False)

    with patch("backend.core.config.get_settings") as mock_settings:
        mock_settings.return_value.security.jwt_private_key = None
        mock_settings.return_value.security.jwt_public_key = None
        mock_settings.return_value.is_testing = False

        with pytest.raises(ValueError, match="RSA keys .* must be provided for RS256 algorithm"):
            JWTService(signing_algorithm="RS256")


@pytest.mark.asyncio
async def test_sec001_jwt_service_succeeds_in_production_with_valid_secret(monkeypatch):
    """Prove that JWTService initializes and generates valid tokens when secret key is provided."""
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("ENVIRONMENT", "production")

    with patch("backend.core.config.get_settings") as mock_settings:
        mock_settings.return_value.security.jwt_secret_key = "production-valid-secret-key-at-least-32-bytes"
        mock_settings.return_value.is_testing = False

        service = JWTService(signing_algorithm="HS256", allowed_algorithms=["HS256"])
        assert service.hmac_secret_key == "production-valid-secret-key-at-least-32-bytes"

        user = MagicMock(id="user-123", email="user@example.com", role="member")
        access_token, _, _ = await service.issue_tokens(user=user)
        payload = await service.verify_token(access_token)
        assert payload.sub == "user-123"


@pytest.mark.asyncio
async def test_sec001_jwt_service_allows_ephemeral_fallback_in_test_mode(monkeypatch):
    """Prove that JWTService allows ephemeral test secret fallback when APP_ENVIRONMENT=testing."""
    monkeypatch.setenv("APP_ENVIRONMENT", "testing")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)

    with patch("backend.core.config.get_settings") as mock_settings:
        mock_settings.return_value.security.jwt_secret_key = None
        mock_settings.return_value.app.secret_key = None
        mock_settings.return_value.is_testing = True

        service = JWTService(signing_algorithm="HS256", allowed_algorithms=["HS256"])
        assert service.hmac_secret_key == "test_ephemeral_jwt_secret_key_for_testing_purposes_only_64b"

        user = MagicMock(id="test-user-456", email="test@example.com", role="admin")
        access_token, _, _ = await service.issue_tokens(user=user)
        payload = await service.verify_token(access_token)
        assert payload.sub == "test-user-456"
