"""PII and Sensitive Data Masking Processor for Structlog."""

from __future__ import annotations

import re
from typing import Any

from structlog.types import EventDict

# Compiled regex patterns for detecting sensitive data inside strings
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]*\b")
_OPENROUTER_KEY_RE = re.compile(r"\bsk-or-v1-[a-f0-9]{64}\b", re.IGNORECASE)
_OPENAI_KEY_RE = re.compile(r"\bsk-(?:proj-)?[a-zA-Z0-9_\-]{20,}\b")
_GEMINI_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b")
_BEARER_TOKEN_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=\-]{20,}\b", re.IGNORECASE)

# Field names whose entire value must be redacted
_MASKED_FIELD_NAMES = frozenset(
    {
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "api_key",
        "client_secret",
        "private_key",
        "jwt",
        "bearer",
        "otp",
        "pin",
        "api_secret",
        "session_secret",
        "id_token",
        "auth_code",
    }
)


def mask_string_value(val: str) -> str:
    """Mask known sensitive patterns (emails, JWTs, API keys) within a string."""
    if not val:
        return val

    # Mask JWTs
    val = _JWT_RE.sub("[JWT_MASKED]", val)
    # Mask API Keys
    val = _OPENROUTER_KEY_RE.sub("[API_KEY_MASKED]", val)
    val = _OPENAI_KEY_RE.sub("[API_KEY_MASKED]", val)
    val = _GEMINI_KEY_RE.sub("[API_KEY_MASKED]", val)
    val = _BEARER_TOKEN_RE.sub("Bearer [TOKEN_MASKED]", val)
    # Mask Emails (preserving domain for debugging context)
    val = _EMAIL_RE.sub(r"[EMAIL:\1]", val)

    return val


def sanitize_data(data: Any) -> Any:
    """Recursively sanitize dictionary, list, or primitive data structures."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_str = str(k).lower()
            if any(sensitive in k_str for sensitive in _MASKED_FIELD_NAMES):
                sanitized[k] = "[MASKED]"
            else:
                sanitized[k] = sanitize_data(v)
        return sanitized
    if isinstance(data, (list, tuple, set)):
        items = [sanitize_data(item) for item in data]
        return type(data)(items) if not isinstance(data, set) else set(items)
    if isinstance(data, str):
        return mask_string_value(data)
    return data


def mask_pii(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Structlog processor that masks PII and credentials across all log fields."""
    try:
        for key, value in list(event_dict.items()):
            key_lower = str(key).lower()
            if any(sensitive in key_lower for sensitive in _MASKED_FIELD_NAMES):
                event_dict[key] = "[MASKED]"
            else:
                event_dict[key] = sanitize_data(value)
    except Exception:
        # PII masking should never fail or crash application logging
        pass
    return event_dict
