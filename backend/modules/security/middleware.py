from backend.modules.security.services.dlp import DLPEngine
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
