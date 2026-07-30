import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from backend.database.engine import get_session_factory
from backend.models.entities.user import User
from backend.document.models.document import Document
from sqlalchemy import select

async def inspect():
    factory = get_session_factory()
    async with factory() as session:
        # 1. Users
        users = await session.execute(select(User))
        users = users.scalars().all()
        print("--- USERS ---")
        for u in users:
            print(f"ID: {u.id} | Email: {u.email} | Role: {u.role} | Tenant: {u.tenant_id} | Name: {getattr(u, 'name', 'N/A')} | Dept: {getattr(u, 'department', 'N/A')}")
        
        docs = await session.execute(select(Document).where(Document.tenant_id == 'default_tenant'))
        docs = docs.scalars().all()
        print(f"\n--- DOCUMENTS (Total: {len(docs)}) ---")
        for d in docs[:20]:
            print(f"Doc: {d.filename} | Status: {d.status} | ID: {d.id}")
        
        print("\n--- SPECIFIC DEMO DOCS ---")
        demo_names = ['hr_policy.txt', 'security_guidelines.txt', 'product_roadmap.txt', 'engineering_handbook.txt']
        demo_docs = [d for d in docs if d.filename in demo_names]
        for d in demo_docs:
            print(f"Doc: {d.filename} | Status: {d.status} | ID: {d.id}")


if __name__ == "__main__":
    asyncio.run(inspect())
