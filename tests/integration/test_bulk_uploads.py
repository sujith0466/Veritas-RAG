import pytest
import sqlalchemy
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.main import app
from backend.core.security.jwt import get_jwt_service
from backend.core.dependencies.database import get_db
from backend.document.models.bulk_batch import BulkBatch

@pytest.mark.asyncio
async def test_bulk_upload_identity_fallback_removed_positive(isolation_test_data):
    data = isolation_test_data
    jwt_service = get_jwt_service()
    
    token_a, _, _ = await jwt_service.issue_tokens(data["user_a"])
    headers_a = {"Authorization": f"Bearer {token_a}"}

    async_session_gen = get_db()
    db = await async_session_gen.__anext__()
    
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {
                "files": [
                    {"filename": "test.pdf", "size_bytes": 1024, "mime_type": "application/pdf"}
                ]
            }
            resp = await client.post("/api/v1/bulk-uploads", json=payload, headers=headers_a)
            assert resp.status_code == 201, resp.text
            
            batch_id = resp.json()["data"]["batch_id"]
            
            # Verify persistence uses the real authenticated owner_id, not a random UUID
            stmt = select(BulkBatch).where(BulkBatch.id == batch_id)
            batch = await db.scalar(stmt)
            
            assert batch is not None
            assert str(batch.tenant_id) == str(data["workspace_a"].id)
            assert str(batch.created_by) == str(data["user_a"].id)
    finally:
        await db.close()

@pytest.mark.asyncio
async def test_bulk_upload_identity_fallback_removed_negative(isolation_test_data):
    data = isolation_test_data
    jwt_service = get_jwt_service()
    
    async_session_gen = get_db()
    db = await async_session_gen.__anext__()
    
    try:
        batch_count_before = await db.scalar(select(sqlalchemy.func.count()).select_from(BulkBatch))
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            payload = {
                "files": [
                    {"filename": "test.pdf", "size_bytes": 1024, "mime_type": "application/pdf"}
                ]
            }
            # We don't send auth headers, so there's no owner_id.
            # If the fallback existed, it might generate a random UUID and succeed.
            # We expect a 401 rejection because no identity could be resolved.
            resp = await client.post("/api/v1/bulk-uploads", json=payload)
            assert resp.status_code == 401
            
        # Prove no batch was persisted with a fabricated identity
        batch_count_after = await db.scalar(select(sqlalchemy.func.count()).select_from(BulkBatch))
        assert batch_count_after == batch_count_before, "A batch was created despite lack of identity!"
        
    finally:
        await db.close()
