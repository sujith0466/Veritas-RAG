import pytest

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
