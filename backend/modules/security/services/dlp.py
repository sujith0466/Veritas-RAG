import re
from backend.modules.security.schemas.security_dto import DLPRedactionResultDTO

class DLPEngine:
    def __init__(self):
        # Basic patterns for demonstration
        self.patterns = {
            "EMAIL": re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
            "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
        }

    def redact(self, text: str) -> DLPRedactionResultDTO:
        redacted_text = text
        entities_redacted = 0
        redaction_types = set()

        for entity_type, pattern in self.patterns.items():
            matches = pattern.findall(redacted_text)
            if matches:
                entities_redacted += len(matches)
                redaction_types.add(entity_type)
                redacted_text = pattern.sub(f"[{entity_type}_REDACTED]", redacted_text)

        return DLPRedactionResultDTO(
            original_text=text,
            redacted_text=redacted_text,
            entities_redacted=entities_redacted,
            redaction_types=list(redaction_types)
        )
