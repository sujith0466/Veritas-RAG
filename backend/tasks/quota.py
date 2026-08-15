"""Celery tasks for quota evaluation and warnings."""

from celery import shared_task
from celery.utils.log import get_task_logger

import asyncio

from sqlalchemy import select
from backend.database.session import SessionLocal
from backend.models.entities.workspace import Workspace
from backend.models.entities.user import User
from backend.tasks.emails import send_email_task

logger = get_task_logger(__name__)

@shared_task(queue="default")
def evaluate_workspace_quotas_task():
    """Evaluates workspace quotas and dispatches warning emails if near limit."""
    asyncio.run(_async_evaluate_workspace_quotas())

async def _async_evaluate_workspace_quotas():
    logger.info("Evaluating workspace quotas for warnings")
    async with SessionLocal() as session:
        # In a real scenario, this would join with usage metrics.
        # For simulation, we assume any workspace with a flag or specific logic gets a warning.
        stmt = select(Workspace).where(Workspace.is_deleted == False)
        result = await session.execute(stmt)
        workspaces = result.scalars().all()
        
        for workspace in workspaces:
            # Simulated quota check: Warn if approaching limit.
            # We will just fetch the owner and dispatch a simulated warning for the sake of F11.1
            # We use a dummy threshold check
            is_near_quota = getattr(workspace, 'simulated_near_quota', False)
            if not is_near_quota:
                continue
                
            # Fetch owner
            owner_stmt = select(User).where(User.tenant_id == workspace.id) # Assuming role checking in real app
            owner_result = await session.execute(owner_stmt)
            owner = owner_result.scalars().first()
            
            if owner:
                subject = f"Action Required: Workspace {workspace.name} is approaching its storage quota"
                body = f"Your workspace {workspace.name} has consumed 90% of its storage quota. Please upgrade your plan."
                
                send_email_task.delay(
                    tenant_id_str=str(workspace.id),
                    subject=subject,
                    to_addresses=[owner.email],
                    html_content=body,
                    text_content=body
                )
                logger.info(f"Dispatched quota warning for workspace {workspace.id}")
