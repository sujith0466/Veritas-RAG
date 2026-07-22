from pydantic import BaseModel


class ChannelConfigDTO(BaseModel):
    channel_type: str
    target_url: str | None = None
    routing_key: str | None = None


class AlertRuleCreateDTO(BaseModel):
    name: str
    metric_name: str
    operator: str
    threshold_value: str
    channels_config: list[ChannelConfigDTO]
    cooldown_minutes: int = 15
    is_active: bool = True


class AlertRuleDTO(AlertRuleCreateDTO):
    id: str
    tenant_id: str


class AlertRuleUpdateDTO(BaseModel):
    is_active: bool


class AlertPayloadDTO(BaseModel):
    tenant_id: str
    rule_name: str
    event_type: str
    metric_name: str
    value: str
    threshold: str


class AlertHistoryDTO(BaseModel):
    id: str
    rule_id: str
    tenant_id: str
    channel_type: str
    status: str
    triggered_at: str
