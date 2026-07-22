from backend.modules.alerts.channels.base import BaseNotificationChannel
from backend.modules.alerts.schemas.alert_dto import (AlertPayloadDTO,
                                                      ChannelConfigDTO)


class SlackChannel(BaseNotificationChannel):
    async def send_alert(
        self, payload: AlertPayloadDTO, config: ChannelConfigDTO
    ) -> bool:
        # Mocking slack webhook delivery
        print(f"SLACK: Sent alert for {payload.rule_name} to {config.target_url}")
        return True
