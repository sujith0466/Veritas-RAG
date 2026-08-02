import uuid

import pytest

from backend.modules.alerts.models.alert_rule import AlertRuleORM
from backend.modules.alerts.schemas.alert_dto import AlertPayloadDTO
from backend.modules.alerts.services.deduplication import AlertDeduplicationEngine
from backend.modules.alerts.services.dispatcher import AlertDispatcher
from backend.modules.alerts.services.rule_engine import AlertRuleEngine


@pytest.mark.asyncio
async def test_rule_engine():
    engine = AlertRuleEngine(AlertDeduplicationEngine(), AlertDispatcher())

    assert engine.evaluate_condition("UNRELIABLE", "EQUALS", "UNRELIABLE") is True
    assert engine.evaluate_condition("50.0", "LESS_THAN", "60.0") is True
    assert engine.evaluate_condition("80.0", "GREATER_THAN", "70.0") is True
    assert engine.evaluate_condition("90.0", "LESS_THAN", "80.0") is False

    payload = AlertPayloadDTO(
        tenant_id="t1",
        rule_name="score_drop",
        event_type="SCORE",
        metric_name="score",
        value="55.0",
        threshold="60.0"
    )
    rule = AlertRuleORM(id=uuid.uuid4(), operator="LESS_THAN", threshold_value="60.0", cooldown_minutes=1, channels_config=[{"channel_type": "SLACK"}])
    await engine.process_event(payload, [rule])
