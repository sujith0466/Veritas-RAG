import asyncio
import structlog
from sqlalchemy import select

from backend.core.config import get_settings
from backend.database.engine import get_session_factory
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_member import WorkspaceMember
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

        # Fetch primary workspace for user
        ws_stmt = select(Workspace).join(WorkspaceMember).where(WorkspaceMember.user_id == admin_user.id).limit(1)
        ws_result = await session.execute(ws_stmt)
        workspace = ws_result.scalar_one_or_none()

        if not workspace:
            logger.error("Admin user lacks a workspace. Bootstrap failed.")
            return

        tenant_id = str(workspace.id)
        owner_id = str(admin_user.id)

    # The run_seed_for_tenant function creates its own session and handles duplicates
    await run_seed_for_tenant(tenant_id, owner_id)

    logger.info("Successfully completed enterprise data seed process")

if __name__ == "__main__":
    asyncio.run(seed_data())
