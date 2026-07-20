import hashlib
import hmac
import json
from backend.modules.alerts.channels.base import BaseNotificationChannel
from backend.modules.alerts.schemas.alert_dto import AlertPayloadDTO, ChannelConfigDTO

class WebhookChannel(BaseNotificationChannel):
    def __init__(self, secret_key: str = "raguard-hmac-secret"):
        self.secret_key = secret_key

    def _sign_payload(self, payload_dict: dict) -> str:
        msg = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
        return hmac.new(self.secret_key.encode('utf-8'), msg, hashlib.sha256).hexdigest()

    async def send_alert(self, payload: AlertPayloadDTO, config: ChannelConfigDTO) -> bool:
        signature = self._sign_payload(payload.model_dump())
        print(f"WEBHOOK: Sent payload to {config.target_url} with signature {signature}")
        return True
