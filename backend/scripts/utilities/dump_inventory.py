import asyncio
from backend.database.engine import get_session_factory
from backend.models.entities.user import User
from backend.document.models.document import Document
from backend.modules.chunking.models.chunk import DocumentChunk
from sqlalchemy import select, func

async def dump():
    factory = get_session_factory()
    async with factory() as session:
        users = await session.execute(select(User).where(User.tenant_id == 'default_tenant'))
        users = users.scalars().all()
        print('--- USERS ---')
        for u in users:
            print(f"Name: {getattr(u, 'name', 'N/A')} | Email: {u.email} | Role: {u.role} | Dept: {getattr(u, 'department', 'N/A')} | Title: {getattr(u, 'job_title', 'N/A')}")
        
        docs = await session.execute(select(Document).where(Document.tenant_id == 'default_tenant'))
        docs = docs.scalars().all()
        print(f'\n--- DOCUMENTS (Total: {len(docs)}) ---')
        
        for d in docs:
            chunks = await session.execute(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == d.id))
            chunk_count = chunks.scalar()
            ready_status = 'Yes' if str(d.status) == 'READY' or str(d.status) == 'DocumentStatus.READY' else 'No'
            print(f'Doc: {d.filename} | Status: {d.status} | Chunks: {chunk_count} | Ready: {ready_status}')

if __name__ == '__main__':
    asyncio.run(dump())
