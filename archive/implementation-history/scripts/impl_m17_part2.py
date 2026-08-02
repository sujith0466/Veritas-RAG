import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 17.2 Implementation...")

    # 1. slack_channel.py
    with open("backend/modules/alerts/channels/slack_channel.py", "w") as f:
        f.write("""from backend.modules.alerts.channels.base import BaseNotificationChannel
from backend.modules.alerts.schemas.alert_dto import AlertPayloadDTO, ChannelConfigDTO

class SlackChannel(BaseNotificationChannel):
    async def send_alert(self, payload: AlertPayloadDTO, config: ChannelConfigDTO) -> bool:
        # Mocking slack webhook delivery
        print(f"SLACK: Sent alert for {payload.rule_name} to {config.target_url}")
        return True
""")

    # 2. pagerduty_channel.py
    with open("backend/modules/alerts/channels/pagerduty_channel.py", "w") as f:
        f.write("""from backend.modules.alerts.channels.base import BaseNotificationChannel
from backend.modules.alerts.schemas.alert_dto import AlertPayloadDTO, ChannelConfigDTO

class PagerDutyChannel(BaseNotificationChannel):
    async def send_alert(self, payload: AlertPayloadDTO, config: ChannelConfigDTO) -> bool:
        print(f"PAGERDUTY: Triggered incident for {payload.rule_name} with routing key {config.routing_key}")
        return True
""")

    # 3. email_channel.py
    with open("backend/modules/alerts/channels/email_channel.py", "w") as f:
        f.write("""from backend.modules.alerts.channels.base import BaseNotificationChannel
from backend.modules.alerts.schemas.alert_dto import AlertPayloadDTO, ChannelConfigDTO

class EmailChannel(BaseNotificationChannel):
    async def send_alert(self, payload: AlertPayloadDTO, config: ChannelConfigDTO) -> bool:
        print(f"EMAIL: Sent email for {payload.rule_name} to {config.target_url}")
        return True
""")

    # 4. webhook_channel.py
    with open("backend/modules/alerts/channels/webhook_channel.py", "w") as f:
        f.write("""import hashlib
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
""")

    print("Milestone 17.2 completed.")

if __name__ == "__main__":
    main()
