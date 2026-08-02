import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 22.3 Implementation...")

    # 1. middleware.py
    with open("backend/modules/security/middleware.py", "w") as f:
        f.write("""from backend.modules.security.services.dlp import DLPEngine
from backend.modules.security.services.auditor import ComplianceAuditor

class SecurityInterceptor:
    def __init__(self, dlp: DLPEngine, auditor: ComplianceAuditor):
        self.dlp = dlp
        self.auditor = auditor

    async def intercept_prompt(self, tenant_id: str, prompt: str) -> str:
        redaction_result = self.dlp.redact(prompt)
        
        if redaction_result.entities_redacted > 0:
            self.auditor.log_event(
                tenant_id=tenant_id,
                actor_id="system",
                action="PII_REDACTED",
                resource="prompt",
                status="SUCCESS"
            )
            
        return redaction_result.redacted_text
""")

    print("Milestone 22.3 completed.")

if __name__ == "__main__":
    main()
