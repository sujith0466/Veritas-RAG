import asyncio
import io
import structlog
from typing import List, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database.engine import get_session_factory
from backend.models.entities.user import User
from backend.document.services.document_service import DocumentService
from backend.document.models import Document

logger = structlog.get_logger(__name__)

def generate_documents() -> List[Dict[str, str]]:
    docs = []
    
    # Generate ~84 documents total
    for i in range(12):
        docs.append({
            "title": f"Leave Policy 202{i%5 + 4}",
            "filename": f"leave_policy_{i}.md",
            "mime_type": "text/markdown",
            "content": f"# Leave Policy\n\nThis is the leave policy document #{i}.\n\n## Paid Time Off (PTO)\nEmployees are entitled to {15 + i} days of PTO annually.\n\n## Sick Leave\nUnlimited sick leave with manager approval.\n\n* Be responsible.\n* Communicate early.",
        })
        docs.append({
            "title": f"Deployment Process V{i}.0",
            "filename": f"deploy_process_{i}.md",
            "mime_type": "text/markdown",
            "content": f"# Deployment Process V{i}.0\n\n## CI/CD Pipeline\nWe use GitHub Actions to deploy to AWS.\n\n```yaml\nname: Deploy\non: push\n```\n\n## Pre-requisites\n- Code review approved\n- Tests passing",
        })
        docs.append({
            "title": f"Password Policy and MFA - {i}",
            "filename": f"password_policy_{i}.txt",
            "mime_type": "text/plain",
            "content": f"Security Guidelines #{i}\n\nAll passwords must be at least 16 characters long. MFA is mandatory. Do not share your password.",
        })
        docs.append({
            "title": f"Product Roadmap Q{i%4 + 1}",
            "filename": f"roadmap_{i}.md",
            "mime_type": "text/markdown",
            "content": f"# Product Roadmap\n\n| Feature | Status | Priority |\n|---|---|---|\n| Enterprise Chat | In Progress | High |\n| Dashboard | Planned | Medium |",
        })
        docs.append({
            "title": f"VPN Setup Guide {i}",
            "filename": f"vpn_setup_{i}.txt",
            "mime_type": "text/plain",
            "content": f"How to setup VPN (Version {i})\n\n1. Download the VPN client from the IT portal.\n2. Install the client.\n3. Login using your SSO credentials.\n4. Connect to the US-East gateway.",
        })
        docs.append({
            "title": f"Expense Policy {i}",
            "filename": f"expense_{i}.md",
            "mime_type": "text/markdown",
            "content": f"# Expense Policy\n\nMeals are covered up to $50 per day during travel. Flights must be booked 14 days in advance.",
        })
        docs.append({
            "title": f"NDA Template {i}",
            "filename": f"nda_{i}.txt",
            "mime_type": "text/plain",
            "content": f"NON-DISCLOSURE AGREEMENT\n\nThis agreement is made between the Company and the Undersigned.\nConfidential information shall not be shared.",
        })
        
    return docs


async def run_seed_for_tenant(tenant_id: str, owner_id):
    logger.info("Starting demo seeding in background", tenant_id=tenant_id)
    doc_service = DocumentService()
    docs = generate_documents()
    
    session_maker = get_session_factory()
    async with session_maker() as session:
        # Check if we already seeded
        stmt = select(Document).where(Document.tenant_id == tenant_id).limit(1)
        existing = await session.execute(stmt)
        if existing.scalar_one_or_none():
            logger.info("Demo data already seeded for tenant. Skipping.", tenant_id=tenant_id)
            return
            
        for doc in docs:
            try:
                stream = io.BytesIO(doc["content"].encode('utf-8'))
                await doc_service.upload_document(
                    stream=stream,
                    filename=doc["filename"],
                    declared_mime=doc["mime_type"],
                    tenant_id=tenant_id,
                    owner_user_id=owner_id,
                    session=session
                )
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to seed doc {doc['title']}: {e}")
        
        await session.commit()
    logger.info("Demo seeding complete", total=len(docs))
