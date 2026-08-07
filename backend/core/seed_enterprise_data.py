import asyncio
import structlog
from sqlalchemy import select

from backend.core.config import get_settings
from backend.database.engine import get_session_factory
from backend.models.entities.user import User
from backend.core.demo_seeder import run_seed_for_tenant

logger = structlog.get_logger(__name__)

async def seed_data():
    logger.info("Starting enterprise data seed process")

    session_maker = get_session_factory()
    async with session_maker() as session:
        qa_email = get_settings().app.qa_email

        # Find QA admin
        stmt = select(User).where(User.email == qa_email)
        result = await session.execute(stmt)
        admin_user = result.scalar_one_or_none()

        if not admin_user:
            logger.error(f"Admin user not found. Please run 'make qa-bootstrap' to provision {qa_email} first.")
            return
            
        if not admin_user.tenant_id:
            logger.error("Admin user lacks a tenant_id. Bootstrap failed.")
            return

        tenant_id = admin_user.tenant_id
        owner_id = admin_user.id
        
    # The run_seed_for_tenant function creates its own session and handles duplicates
    await run_seed_for_tenant(tenant_id, owner_id)
    
    logger.info("Successfully completed enterprise data seed process")

if __name__ == "__main__":
    asyncio.run(seed_data())
