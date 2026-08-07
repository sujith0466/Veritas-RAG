import asyncio
import datetime
import uuid
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.config import get_settings
from backend.database.engine import get_session_factory
from backend.api.v1.schemas.registration import RegistrationRequest
from backend.services.auth.registration_service import RegistrationService
from backend.repositories.implementations.user_repository import UserRepository

logger = structlog.get_logger(__name__)

async def bootstrap_qa():
    """Idempotent bootstrap script to provision a QA Admin user and Tenant."""
    logger.info("Starting QA Environment Bootstrap...")

    settings = get_settings()
    qa_email = getattr(settings, "qa_email", "qa@raguard.ai")
    qa_password = getattr(settings, "qa_password", "RaguardQA2026!")

    session_maker = get_session_factory()
    async with session_maker() as session:
        user_repo = UserRepository(session)
        
        # Check if QA user already exists
        existing_user = await user_repo.get_by_email(qa_email)
        if existing_user:
            logger.info("QA user already exists. Checking roles/tenant...", user_id=str(existing_user.id))
            if existing_user.tenant_id is None:
                existing_user.tenant_id = str(uuid.uuid4())
                logger.info("Assigned new tenant_id to existing QA user.")
            
            if not existing_user.is_verified:
                existing_user.is_verified = True
                existing_user.verified_at = datetime.datetime.utcnow()
                logger.info("Verified existing QA user.")
                
            if existing_user.role != "admin":
                existing_user.role = "admin"
                logger.info("Promoted QA user to admin.")

            await session.commit()
            logger.info("QA Bootstrap Complete (Idempotent).")
            return

        logger.info("Creating QA user...")
        # 1. Use RegistrationService to handle standard creation, password hashing, and token generation
        reg_service = RegistrationService(session)
        req = RegistrationRequest(
            email=qa_email,
            password=qa_password,
            full_name="QA Admin"
        )
        
        # We need to temporarily disable email sending since we might not have a configured email provider in local dev
        # Wait, RegistrationService calls `get_email_provider().send_verification_email()`.
        # In development, the MockEmailProvider handles this without error.
        await reg_service.register_user(req)
        
        # 2. Fetch the newly created user to elevate privileges and assign tenant
        new_user = await user_repo.get_by_email(qa_email)
        if not new_user:
            logger.error("Failed to retrieve QA user after registration.")
            return
            
        new_user.is_verified = True
        new_user.verified_at = datetime.datetime.utcnow()
        new_user.role = "admin"
        new_user.tenant_id = str(uuid.uuid4())
        new_user.workspace_name = "QA Workspace"
        
        await session.commit()
        
        logger.info(
            "QA Bootstrap Complete. Account created.", 
            email=qa_email, 
            tenant=new_user.tenant_id
        )

if __name__ == "__main__":
    asyncio.run(bootstrap_qa())
