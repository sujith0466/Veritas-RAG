"""Unit and Security Tests for Structured Logging and PII Masking (F14.3)."""

from unittest.mock import MagicMock

from backend.core.logging.config import _add_otel_context
from backend.core.logging.middleware import _sanitize_query_string
from backend.observability.logging.pii_masker import (
    mask_pii,
    mask_string_value,
    sanitize_data,
)


class TestPIIMasking:
    """Test suite for PII & Credential Scrubbing."""

    def test_mask_email_in_string(self) -> None:
        raw = "User email is john.doe@raguard.ai and backup is admin@corp.org"
        masked = mask_string_value(raw)
        assert "john.doe" not in masked
        assert "admin@" not in masked
        assert "[EMAIL:raguard.ai]" in masked
        assert "[EMAIL:corp.org]" in masked

    def test_mask_jwt_in_string(self) -> None:
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        raw = f"Bearer token generated: {jwt}"
        masked = mask_string_value(raw)
        assert jwt not in masked
        assert "[JWT_MASKED]" in masked

    def test_mask_api_keys(self) -> None:
        mock_generic_key = "sk-mocktestkey-1234567890abcdef1234567890abcdef"
        openai_key = "sk-abcdef123456789012345678901234567890"
        gemini_key = "AIzaSyD-1234567890abcdefghijklmnopqrstuv"
        bearer = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abcdef1234567890"

        assert "[API_KEY_MASKED]" in mask_string_value(f"Key is {mock_generic_key}")
        assert mock_generic_key not in mask_string_value(f"Key is {mock_generic_key}")

        assert "[API_KEY_MASKED]" in mask_string_value(f"OpenAI key: {openai_key}")
        assert openai_key not in mask_string_value(f"OpenAI key: {openai_key}")

        assert "[API_KEY_MASKED]" in mask_string_value(f"Gemini key: {gemini_key}")
        assert gemini_key not in mask_string_value(f"Gemini key: {gemini_key}")

        assert "Bearer [TOKEN_MASKED]" in mask_string_value(f"Header: {bearer}")

    def test_mask_sensitive_dictionary_keys(self) -> None:
        payload = {
            "username": "developer",
            "password": "SuperSecretPassword123!",
            "api_key": "some-secret-api-key",
            "access_token": "token-value-xyz",
            "refresh_token": "refresh-value-123",
            "authorization": "Bearer secret-auth-token",
            "client_secret": "my-client-secret",
            "otp": "123456",
            "pin": "9876",
        }
        sanitized = sanitize_data(payload)
        assert sanitized["username"] == "developer"
        assert sanitized["password"] == "[MASKED]"
        assert sanitized["api_key"] == "[MASKED]"
        assert sanitized["access_token"] == "[MASKED]"
        assert sanitized["refresh_token"] == "[MASKED]"
        assert sanitized["authorization"] == "[MASKED]"
        assert sanitized["client_secret"] == "[MASKED]"
        assert sanitized["otp"] == "[MASKED]"
        assert sanitized["pin"] == "[MASKED]"

    def test_mask_nested_structures(self) -> None:
        payload = {
            "event": "user_action",
            "metadata": {
                "user": {"email": "alice@company.com", "secret": "shhh"},
                "tags": ["admin", "token=secret_val_12345"],
            },
        }
        sanitized = sanitize_data(payload)
        assert sanitized["metadata"]["user"]["secret"] == "[MASKED]"
        assert "[EMAIL:company.com]" in sanitized["metadata"]["user"]["email"]

    def test_structlog_processor_integration(self) -> None:
        event_dict = {
            "event": "Login attempted for user@domain.com",
            "password": "RawPassword!",
            "workspace_id": "ws-12345",
            "service": "raguard-ai",
        }
        processed = mask_pii(None, "info", event_dict)
        assert processed["service"] == "raguard-ai"
        assert processed["workspace_id"] == "ws-12345"
        assert processed["password"] == "[MASKED]"
        assert "[EMAIL:domain.com]" in processed["event"]
        assert "user@domain.com" not in processed["event"]


class TestQueryStringSanitizer:
    """Test suite for URL query parameter sanitization."""

    def test_clean_query_preserves_safe_params(self) -> None:
        query = "page=1&limit=20&sort=desc&filter=documents"
        sanitized = _sanitize_query_string(query)
        assert sanitized == "page=1&limit=20&sort=desc&filter=documents"

    def test_sanitizes_sensitive_params(self) -> None:
        query = "page=1&token=my_secret_token_123&api_key=sk-123456&code=auth_code_xyz"
        sanitized = _sanitize_query_string(query)
        assert "token=%5BMASKED%5D" in sanitized or "token=[MASKED]" in sanitized
        assert "my_secret_token_123" not in sanitized
        assert "sk-123456" not in sanitized
        assert "auth_code_xyz" not in sanitized
        assert "page=1" in sanitized

    def test_empty_and_none_query(self) -> None:
        assert _sanitize_query_string("") is None


class TestOTelLoggingContext:
    """Test suite for OpenTelemetry context injection into structured logs."""

    def test_otel_context_injected_when_span_active(self) -> None:
        from unittest.mock import patch

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_ctx = MagicMock()
        mock_ctx.trace_id = 0x4BF92F3577B34DA6A3CE929D0E0E4736
        mock_ctx.span_id = 0x00F067AA0BA902B7
        mock_span.get_span_context.return_value = mock_ctx

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            event_dict = {"event": "test log"}
            result = _add_otel_context(None, "info", event_dict)
            assert result["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
            assert result["span_id"] == "00f067aa0ba902b7"

    def test_otel_context_safely_ignored_when_no_span(self) -> None:
        from unittest.mock import patch

        mock_span = MagicMock()
        mock_span.is_recording.return_value = False

        with patch("opentelemetry.trace.get_current_span", return_value=mock_span):
            event_dict = {"event": "test log"}
            result = _add_otel_context(None, "info", event_dict)
            assert "trace_id" not in result
            assert "span_id" not in result
