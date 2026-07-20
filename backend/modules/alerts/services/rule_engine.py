from backend.modules.alerts.models.alert_rule import AlertRuleORM
from backend.modules.alerts.schemas.alert_dto import AlertPayloadDTO
from backend.modules.alerts.services.deduplication import AlertDeduplicationEngine
from backend.modules.alerts.services.dispatcher import AlertDispatcher

class AlertRuleEngine:
    def __init__(self, dedup: AlertDeduplicationEngine, dispatcher: AlertDispatcher):
        self.dedup = dedup
        self.dispatcher = dispatcher

    def evaluate_condition(self, value: str, operator: str, threshold: str) -> bool:
        if operator == "EQUALS":
            return value == threshold
        try:
            v_float = float(value)
            t_float = float(threshold)
            if operator == "LESS_THAN":
                return v_float < t_float
            if operator == "GREATER_THAN":
                return v_float > t_float
        except ValueError:
            pass
        return False

    async def process_event(self, event_payload: AlertPayloadDTO, rules: list[AlertRuleORM]):
        for rule in rules:
            if self.evaluate_condition(event_payload.value, rule.operator, rule.threshold_value):
                can_trigger = await self.dedup.check_and_set_cooldown(rule.id, rule.cooldown_minutes)
                if can_trigger:
                    await self.dispatcher.dispatch_async(rule, event_payload)
