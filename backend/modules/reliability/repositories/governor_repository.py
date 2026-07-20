from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.modules.reliability.models.self_healing_policy import SelfHealingPolicyORM
from backend.modules.reliability.models.healing_action_log import HealingActionLogORM

class GovernorRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_policy(self, tenant_id: str) -> SelfHealingPolicyORM | None:
        query = select(SelfHealingPolicyORM).where(SelfHealingPolicyORM.tenant_id == tenant_id)
        res = await self._session.execute(query)
        return res.scalar_one_or_none()

    async def save_action_log(self, log: HealingActionLogORM) -> HealingActionLogORM:
        self._session.add(log)
        await self._session.commit()
        return log
