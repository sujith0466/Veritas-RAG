import pytest
import uuid
from backend.modules.alerts.services.deduplication import AlertDeduplicationEngine

@pytest.mark.asyncio
async def test_deduplication():
    engine = AlertDeduplicationEngine()
    rule_id = uuid.uuid4()
    
    # First time should trigger
    assert await engine.check_and_set_cooldown(rule_id, 15) is True
    
    # Second time should be suppressed
    assert await engine.check_and_set_cooldown(rule_id, 15) is False
