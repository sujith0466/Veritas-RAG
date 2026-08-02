import os
import subprocess
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 17.4 Implementation (Tests)...")
    os.makedirs("tests/unit/backend/modules/alerts", exist_ok=True)
    os.makedirs("tests/integration", exist_ok=True)

    # 1. test_rule_engine.py
    with open("tests/unit/backend/modules/alerts/test_rule_engine.py", "w") as f:
        f.write("""import pytest
import uuid
from backend.modules.alerts.services.rule_engine import AlertRuleEngine
from backend.modules.alerts.services.deduplication import AlertDeduplicationEngine
from backend.modules.alerts.services.dispatcher import AlertDispatcher
from backend.modules.alerts.schemas.alert_dto import AlertPayloadDTO
from backend.modules.alerts.models.alert_rule import AlertRuleORM

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
""")

    # 2. test_deduplication.py
    with open("tests/unit/backend/modules/alerts/test_deduplication.py", "w") as f:
        f.write("""import pytest
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
""")

    # 3. test_channels.py
    with open("tests/unit/backend/modules/alerts/test_channels.py", "w") as f:
        f.write("""import pytest
from backend.modules.alerts.channels.slack_channel import SlackChannel
from backend.modules.alerts.channels.webhook_channel import WebhookChannel
from backend.modules.alerts.schemas.alert_dto import AlertPayloadDTO, ChannelConfigDTO

@pytest.mark.asyncio
async def test_slack_channel():
    channel = SlackChannel()
    payload = AlertPayloadDTO(tenant_id="t1", rule_name="r1", event_type="e1", metric_name="m1", value="v1", threshold="t1")
    config = ChannelConfigDTO(channel_type="SLACK", target_url="http://test")
    assert await channel.send_alert(payload, config) is True

@pytest.mark.asyncio
async def test_webhook_channel():
    channel = WebhookChannel("secret")
    payload = AlertPayloadDTO(tenant_id="t1", rule_name="r1", event_type="e1", metric_name="m1", value="v1", threshold="t1")
    config = ChannelConfigDTO(channel_type="WEBHOOK", target_url="http://test")
    assert await channel.send_alert(payload, config) is True
""")

    print("Created test files.")

    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/backend/modules/alerts"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    print("Milestone 17.4 completed.")

if __name__ == "__main__":
    main()
