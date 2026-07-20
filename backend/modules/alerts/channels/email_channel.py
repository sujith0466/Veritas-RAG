from backend.modules.alerts.channels.base import BaseNotificationChannel
from backend.modules.alerts.schemas.alert_dto import AlertPayloadDTO, ChannelConfigDTO

class EmailChannel(BaseNotificationChannel):
    async def send_alert(self, payload: AlertPayloadDTO, config: ChannelConfigDTO) -> bool:
        print(f"EMAIL: Sent email for {payload.rule_name} to {config.target_url}")
        return True
