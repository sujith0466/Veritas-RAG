import pytest

from backend.modules.security.middleware import SecurityInterceptor
from backend.modules.security.services.auditor import ComplianceAuditor
from backend.modules.security.services.dlp import DLPEngine


@pytest.mark.asyncio
async def test_security_interceptor():
    dlp = DLPEngine()
    auditor = ComplianceAuditor()
    interceptor = SecurityInterceptor(dlp, auditor)

    clean_prompt = await interceptor.intercept_prompt("t1", "Just a normal question.")
    assert clean_prompt == "Just a normal question."

    dirty_prompt = await interceptor.intercept_prompt("t1", "My SSN is 123-45-6789")
    assert "[SSN_REDACTED]" in dirty_prompt
