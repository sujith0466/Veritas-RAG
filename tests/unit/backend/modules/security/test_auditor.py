import pytest
from backend.modules.security.services.auditor import ComplianceAuditor

def test_compliance_auditor():
    auditor = ComplianceAuditor()
    event = auditor.log_event("t1", "user1", "VIEW_CLASSIFIED", "document_123")
    
    assert event.tenant_id == "t1"
    assert event.action == "VIEW_CLASSIFIED"
    assert event.status == "SUCCESS"
