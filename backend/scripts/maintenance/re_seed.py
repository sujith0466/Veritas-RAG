import asyncio
from backend.core.demo_seeder import run_seed_for_tenant
from backend.database.engine import get_session_factory
from backend.models.entities.user import User
from sqlalchemy import select, text

async def main():
    session_maker = get_session_factory()
    async with session_maker() as session:
        admin = (await session.execute(select(User).where(User.email == "demoadmin@gmail.com"))).scalar_one_or_none()
        
        # Delete existing documents so it runs again
        await session.execute(text("DELETE FROM document_events"))
        await session.execute(text("DELETE FROM processing_jobs"))
        await session.execute(text("DELETE FROM document_versions"))
        await session.execute(text("DELETE FROM documents"))
        await session.commit()
        print("Cleared previous docs.")
        
        await run_seed_for_tenant(admin.tenant_id, admin.id)
        
if __name__ == "__main__":
    asyncio.run(main())
