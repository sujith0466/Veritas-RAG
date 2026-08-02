from abc import ABC, abstractmethod

from backend.modules.alerts.schemas.alert_dto import AlertPayloadDTO, ChannelConfigDTO


class BaseNotificationChannel(ABC):
    @abstractmethod
    async def send_alert(
        self, payload: AlertPayloadDTO, config: ChannelConfigDTO
    ) -> bool:
        pass
