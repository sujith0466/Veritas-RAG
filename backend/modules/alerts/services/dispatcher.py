from backend.modules.alerts.channels.email_channel import EmailChannel
from backend.modules.alerts.channels.pagerduty_channel import PagerDutyChannel
from backend.modules.alerts.channels.slack_channel import SlackChannel
from backend.modules.alerts.channels.webhook_channel import WebhookChannel
from backend.modules.alerts.models.alert_rule import AlertRuleORM
from backend.modules.alerts.schemas.alert_dto import AlertPayloadDTO, ChannelConfigDTO


class AlertDispatcher:
    def __init__(self):
        self.channels = {
            "SLACK": SlackChannel(),
            "PAGERDUTY": PagerDutyChannel(),
            "EMAIL": EmailChannel(),
            "WEBHOOK": WebhookChannel(),
        }

    async def dispatch_async(self, rule: AlertRuleORM, payload: AlertPayloadDTO):
        for config_dict in rule.channels_config:
            config = ChannelConfigDTO(**config_dict)
            channel = self.channels.get(config.channel_type)
            if channel:
                success = await channel.send_alert(payload, config)
                # In production, save AlertHistoryORM via repository here
