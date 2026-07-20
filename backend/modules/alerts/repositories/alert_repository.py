from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.modules.alerts.models.alert_rule import AlertRuleORM
from backend.modules.alerts.models.alert_history import AlertHistoryORM

class AlertRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_active_rules(self, tenant_id: str, metric_name: str) -> list[AlertRuleORM]:
        query = select(AlertRuleORM).where(
            AlertRuleORM.tenant_id == tenant_id,
            AlertRuleORM.metric_name == metric_name,
            AlertRuleORM.is_active == True
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())
        
    async def save_history(self, history: AlertHistoryORM) -> AlertHistoryORM:
        self._session.add(history)
        await self._session.commit()
        return history
