from datetime import datetime
import json
import structlog

from backend.modules.security.schemas.security_dto import AuditEventDTO


class ComplianceAuditor:
    def __init__(self):
        self.logger = structlog.get_logger("compliance_audit")

    def log_event(
        self,
        tenant_id: str,
        actor_id: str,
        action: str,
        resource: str,
        status: str = "SUCCESS",
    ):
        event = AuditEventDTO(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            resource=resource,
            status=status,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        # In a real system, this might write to a secure WORM drive or separate audit DB
        self.logger.info(json.dumps(event.model_dump()))
        return event
