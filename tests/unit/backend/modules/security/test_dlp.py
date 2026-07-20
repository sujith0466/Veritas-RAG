import pytest
from backend.modules.security.services.dlp import DLPEngine

def test_dlp_engine():
    engine = DLPEngine()
    result = engine.redact("My email is test@example.com and SSN is 123-45-6789.")
    
    assert result.entities_redacted == 2
    assert "test@example.com" not in result.redacted_text
    assert "123-45-6789" not in result.redacted_text
    assert "[EMAIL_REDACTED]" in result.redacted_text
    assert "[SSN_REDACTED]" in result.redacted_text
    assert set(result.redaction_types) == {"EMAIL", "SSN"}
