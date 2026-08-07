import asyncio

from sqlalchemy import select, text

from backend.core.demo_seeder import run_seed_for_tenant
from backend.database.engine import get_session_factory
from backend.models.entities.user import User


from backend.core.config import get_settings

async def main():
    session_maker = get_session_factory()
    async with session_maker() as session:
        qa_email = get_settings().app.qa_email
        admin = (await session.execute(select(User).where(User.email == qa_email))).scalar_one_or_none()
        
        if not admin:
            print(f"User {qa_email} not found. Please run 'make qa-bootstrap'.")
            return

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
