import pytest
from httpx import AsyncClient, ASGITransport
import uuid
import asyncio

from backend.main import app
from backend.core.security.jwt import get_jwt_service
from backend.core.config import get_settings
from backend.modules.vector.providers.qdrant_provider import QdrantVectorDBProvider
from backend.modules.vector.schemas.payload import VectorPointDTO

@pytest.mark.asyncio
async def test_cross_workspace_retrieval_isolation(isolation_test_data, mocker):
    """
    Genuine integration test demonstrating that users cannot retrieve content from workspaces
    they do not belong to, and that spoofing X-Tenant-ID is ignored in favor of the real
    WorkspaceContext provided by their JWT. Uses real Qdrant vectors.
    """
    data = isolation_test_data
    jwt_service = get_jwt_service()
    settings = get_settings()
    
    ws_a_id = str(data["workspace_a"].id)
    ws_b_id = str(data["workspace_b"].id)
    
    from qdrant_client import AsyncQdrantClient
    # Use 127.0.0.1 to avoid IPv6 localhost resolution issues in Windows/WSL
    real_client = AsyncQdrantClient(host="127.0.0.1", port=6333)
    mocker.patch("backend.modules.vector.providers.qdrant_provider.get_qdrant_client", return_value=real_client)
    
    # 1. Setup Data in Qdrant (Real data path)
    settings = get_settings()
    settings.qdrant.host = "127.0.0.1"
    
    qdrant = QdrantVectorDBProvider()
    
    from backend.modules.vector.schemas.payload import CollectionConfigDTO
    # We create vector collections for WS A and WS B using the exact system logic
    col_a = settings.qdrant.collection_name(ws_a_id)
    col_b = settings.qdrant.collection_name(ws_b_id)
    
    await qdrant.ensure_collection(CollectionConfigDTO(collection_name=col_a, dimension=384))
    await qdrant.ensure_collection(CollectionConfigDTO(collection_name=col_b, dimension=384))

    # Note: Using dimension=384 to match all-MiniLM-L6-v2 output
    vector_a = [0.1] * 384
    vector_b = [0.2] * 384

    # Insert distinct points
    doc_id_a = uuid.uuid4()
    doc_id_b = uuid.uuid4()
    
    point_a = VectorPointDTO(
        point_id=uuid.uuid5(uuid.NAMESPACE_DNS, "ws_a_content"),
        vector=vector_a,
        payload={
            "tenant_id": ws_a_id,
            "document_id": str(doc_id_a),
            "document_version_id": str(uuid.uuid4()),
            "content_hash": "hash_a",
            "content": "This is Workspace A secret project document."
        }
    )
    
    point_b = VectorPointDTO(
        point_id=uuid.uuid5(uuid.NAMESPACE_DNS, "ws_b_content"),
        vector=vector_b,
        payload={
            "tenant_id": ws_b_id,
            "document_id": str(doc_id_b),
            "document_version_id": str(uuid.uuid4()),
            "content_hash": "hash_b",
            "content": "This is Workspace B highly confidential file."
        }
    )

    await qdrant.upsert_points(col_a, [point_a])
    await qdrant.upsert_points(col_b, [point_b])
    
    # Initialize BM25 Sparse Index
    from backend.modules.retrieval.api.dependencies import _bm25_provider
    class DummyChunk:
        pass
    chunk_a = DummyChunk()
    chunk_a.id = str(uuid.uuid4())
    chunk_a.document_id = str(doc_id_a)
    chunk_a.document_version_id = str(uuid.uuid4())
    chunk_a.tenant_id = ws_a_id
    chunk_a.content = point_a.payload['content']
    
    chunk_b = DummyChunk()
    chunk_b.id = str(uuid.uuid4())
    chunk_b.document_id = str(doc_id_b)
    chunk_b.document_version_id = str(uuid.uuid4())
    chunk_b.tenant_id = ws_b_id
    chunk_b.content = point_b.payload['content']
    
    await _bm25_provider.index_chunks(ws_a_id, [chunk_a])
    await _bm25_provider.index_chunks(ws_b_id, [chunk_b])

    # Let Qdrant index settle
    await asyncio.sleep(0.5)

    # 2. Issue JWTs
    token_a, _, _ = await jwt_service.issue_tokens(data["user_a"])
    token_b, _, _ = await jwt_service.issue_tokens(data["user_b"])
    token_c, _, _ = await jwt_service.issue_tokens(data["user_c"]) # user_c has no workspace membership
    
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    headers_c = {"Authorization": f"Bearer {token_c}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        search_payload_a = {"query": "secret project documents", "top_k": 3}
        
        # Case A: User A -> Workspace A
        resp_a = await client.post("/api/v1/retrieval/search", json=search_payload_a, headers=headers_a)
        assert resp_a.status_code == 200, resp_a.text
        res_a_data = resp_a.json()["data"]["final_evidence"]
        
        for item in res_a_data:
            assert item["tenant_id"] == ws_a_id
            assert "Workspace A" in item["content"]
            assert "Workspace B" not in item["content"]
        
        # Case B: User A spoofing X-Tenant-ID
        headers_a_malicious = {
            "Authorization": f"Bearer {token_a}",
            "X-Tenant-ID": ws_b_id  # Attempting to access Workspace B
        }
        resp_malicious = await client.post("/api/v1/retrieval/search", json=search_payload_a, headers=headers_a_malicious)
        assert resp_malicious.status_code == 200, resp_malicious.text
        res_malicious_data = resp_malicious.json()["data"]["final_evidence"]
        
        for item in res_malicious_data:
            assert item["tenant_id"] == ws_a_id
            assert "Workspace A" in item["content"]
            assert "Workspace B" not in item["content"]
            
        # Case C: User B -> Workspace B
        resp_b = await client.post("/api/v1/retrieval/search", json=search_payload_a, headers=headers_b)
        assert resp_b.status_code == 200, resp_b.text
        res_b_data = resp_b.json()["data"]["final_evidence"]
        
        for item in res_b_data:
            assert item["tenant_id"] == ws_b_id
            assert "Workspace B" in item["content"]
            assert "Workspace A" not in item["content"]
        
        # Case D: User C (no workspace membership)
        resp_c = await client.post("/api/v1/retrieval/search", json=search_payload_a, headers=headers_c)
        # Unauthorized vs Forbidden based on exact RBAC route rejection
        assert resp_c.status_code in (401, 403)
        
        print(f"\nUSER_A_ID={data['user_a'].id}")
        print(f"WORKSPACE_A_ID={ws_a_id}")
        print(f"WORKSPACE_A_CONTENT={point_a.payload['content']}")
        print(f"USER_A_RETRIEVED_CONTENT={[item['content'] for item in res_a_data]}")
        print(f"WORKSPACE_B_ID={ws_b_id}")
        print(f"WORKSPACE_B_CONTENT={point_b.payload['content']}")
        ws_b_absent = all(item["tenant_id"] != ws_b_id and "Workspace B" not in item["content"] for item in res_a_data)
        print(f"WORKSPACE_B_ABSENCE_CHECK={ws_b_absent}")
        print(f"SPOOFED_RETRIEVED_CONTENT={[item['content'] for item in res_malicious_data]}")
        print(f"USER_B_RETRIEVED_CONTENT={[item['content'] for item in res_b_data]}")
        print(f"UNAUTHORIZED_RETRIEVED_CONTENT={resp_c.json() if resp_c.status_code != 403 else '[]'} (Status: {resp_c.status_code})\n")
        
        # Case E: Unauthenticated search
        resp_unauth = await client.post("/api/v1/retrieval/search", json=search_payload_a, headers={"X-Tenant-ID": ws_a_id})
        assert resp_unauth.status_code == 401

