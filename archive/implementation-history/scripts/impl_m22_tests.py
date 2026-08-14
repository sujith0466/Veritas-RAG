import os
import subprocess
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 22.4 Implementation (Tests)...")
    os.makedirs("tests/unit/backend/modules/security", exist_ok=True)

    # 1. test_dlp.py
    with open("tests/unit/backend/modules/security/test_dlp.py", "w") as f:
        f.write("""import pytest
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
""")

    # 2. test_auditor.py
    with open("tests/unit/backend/modules/security/test_auditor.py", "w") as f:
        f.write("""import pytest
from backend.modules.security.services.auditor import ComplianceAuditor

def test_compliance_auditor():
    auditor = ComplianceAuditor()
    event = auditor.log_event("t1", "user1", "VIEW_CLASSIFIED", "document_123")
    
    assert event.tenant_id == "t1"
    assert event.action == "VIEW_CLASSIFIED"
    assert event.status == "SUCCESS"
""")

    # 3. test_middleware.py
    with open("tests/unit/backend/modules/security/test_middleware.py", "w") as f:
        f.write("""import pytest
from backend.modules.security.security_interceptor import SecurityInterceptor
from backend.modules.security.services.dlp import DLPEngine
from backend.modules.security.services.auditor import ComplianceAuditor

@pytest.mark.asyncio
async def test_security_interceptor():
    dlp = DLPEngine()
    auditor = ComplianceAuditor()
    interceptor = SecurityInterceptor(dlp, auditor)
    
    clean_prompt = await interceptor.intercept_prompt("t1", "Just a normal question.")
    assert clean_prompt == "Just a normal question."
    
    dirty_prompt = await interceptor.intercept_prompt("t1", "My SSN is 123-45-6789")
    assert "[SSN_REDACTED]" in dirty_prompt
""")

    print("Created test files.")

    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/backend/modules/security"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    print("Milestone 22.4 completed.")

if __name__ == "__main__":
    main()
