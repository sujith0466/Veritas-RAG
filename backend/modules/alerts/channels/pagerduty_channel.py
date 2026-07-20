from backend.modules.alerts.channels.base import BaseNotificationChannel
from backend.modules.alerts.schemas.alert_dto import AlertPayloadDTO, ChannelConfigDTO

class PagerDutyChannel(BaseNotificationChannel):
    async def send_alert(self, payload: AlertPayloadDTO, config: ChannelConfigDTO) -> bool:
        print(f"PAGERDUTY: Triggered incident for {payload.rule_name} with routing key {config.routing_key}")
        return True
