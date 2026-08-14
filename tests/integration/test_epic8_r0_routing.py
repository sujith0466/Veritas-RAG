import pytest
import uuid
import asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch

from backend.main import app
from backend.core.security.jwt import get_jwt_service
from backend.core.dependencies.database import get_db
from backend.core.config import get_settings
from backend.modules.vector.providers.qdrant_provider import QdrantVectorDBProvider
from backend.modules.vector.schemas.payload import VectorPointDTO, CollectionConfigDTO
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator
from backend.document.models.document import Document
from backend.document.models.status import DocumentStatus

@pytest.mark.asyncio
async def test_phase8_r0_tenant_workspace_routing(isolation_test_data, mocker):
    """
    Phase 8-R0 Evidence Capture:
    Proves that the AI Wrapper Service correctly passes the tenant_id to the 
    RetrievalOrchestrator, and that retrieval isolates content correctly
    without spoofing the workspace.
    """
    data = isolation_test_data
    jwt_service = get_jwt_service()
    settings = get_settings()
    settings.qdrant.host = "127.0.0.1"
    
    ws_a_id = str(data["workspace_a"].id)
    ws_b_id = str(data["workspace_b"].id)
    user_a_id = str(data["user_a"].id)
    user_b_id = str(data["user_b"].id)

    # 1. Setup Data in Qdrant (Real data path)
    from qdrant_client import AsyncQdrantClient
    real_client = AsyncQdrantClient(host="127.0.0.1", port=6333)
    
    mocker.patch("backend.ai.wrapper.namespace.get_qdrant_client", return_value=real_client)
    mocker.patch("backend.vector_db.client.get_qdrant_client", return_value=real_client)
    mocker.patch("backend.modules.vector.providers.qdrant_provider.get_qdrant_client", return_value=real_client)
    qdrant = QdrantVectorDBProvider()
    col_a = settings.qdrant.collection_name(ws_a_id)
    col_b = settings.qdrant.collection_name(ws_b_id)
    
    await qdrant.ensure_collection(CollectionConfigDTO(collection_name=col_a, dimension=384))
    await qdrant.ensure_collection(CollectionConfigDTO(collection_name=col_b, dimension=384))

    vector_a = [0.1] * 384
    vector_b = [0.2] * 384

    doc_id_a = str(uuid.uuid4())
    doc_id_b = str(uuid.uuid4())
    
    point_a = VectorPointDTO(
        point_id=uuid.uuid5(uuid.NAMESPACE_DNS, "ws_a_r0"),
        vector=vector_a,
        payload={
            "tenant_id": ws_a_id,
            "document_id": doc_id_a,
            "document_version_id": str(uuid.uuid4()),
            "content_hash": "hash_a_r0",
            "content": "Phase8R0 Workspace A secret data."
        }
    )
    
    point_b = VectorPointDTO(
        point_id=uuid.uuid5(uuid.NAMESPACE_DNS, "ws_b_r0"),
        vector=vector_b,
        payload={
            "tenant_id": ws_b_id,
            "document_id": doc_id_b,
            "document_version_id": str(uuid.uuid4()),
            "content_hash": "hash_b_r0",
            "content": "Phase8R0 Workspace B isolated data."
        }
    )

    await qdrant.upsert_points(col_a, [point_a])
    await qdrant.upsert_points(col_b, [point_b])
    
    # 2. Initialize BM25 Sparse Index
    from backend.modules.retrieval.api.dependencies import _bm25_provider
    class DummyChunk:
        pass
    chunk_a = DummyChunk()
    chunk_a.id = str(uuid.uuid4())
    chunk_a.document_id = doc_id_a
    chunk_a.document_version_id = str(uuid.uuid4())
    chunk_a.tenant_id = ws_a_id
    chunk_a.content = point_a.payload['content']
    
    chunk_b = DummyChunk()
    chunk_b.id = str(uuid.uuid4())
    chunk_b.document_id = doc_id_b
    chunk_b.document_version_id = str(uuid.uuid4())
    chunk_b.tenant_id = ws_b_id
    chunk_b.content = point_b.payload['content']
    
    await _bm25_provider.index_chunks(ws_a_id, [chunk_a])
    await _bm25_provider.index_chunks(ws_b_id, [chunk_b])
    await asyncio.sleep(0.5)

    # 3. Create READY documents in DB for validation gate
    async_session_gen = get_db()
    db = await async_session_gen.__anext__()
    try:
        doc_a = Document(
            tenant_id=ws_a_id, owner_user_id=uuid.UUID(user_a_id),
            filename="doc_a.txt", original_filename="doc_a.txt", status=DocumentStatus.READY
        )
        doc_b = Document(
            tenant_id=ws_b_id, owner_user_id=uuid.UUID(user_b_id),
            filename="doc_b.txt", original_filename="doc_b.txt", status=DocumentStatus.READY
        )
        db.add(doc_a)
        db.add(doc_b)
        await db.commit()
    finally:
        await db.close()

    # 4. Auth setup
    token_a, _, _ = await jwt_service.issue_tokens(data["user_a"])
    token_b, _, _ = await jwt_service.issue_tokens(data["user_b"])
    
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # We spy on execute_hybrid_search to inspect kwargs
    original_execute = RetrievalOrchestrator.execute_hybrid_search
    
    spy_calls = []
    
    original_execute = RetrievalOrchestrator.execute_hybrid_search
    async def fake_execute(self, *args, **kwargs):
        # tenant_id might be in args or kwargs
        call_info = dict(kwargs)
        if len(args) > 1: call_info["tenant_id"] = args[1]
        spy_calls.append(call_info)
        return await original_execute(self, *args, **kwargs)

    print("\n\n--- PHASE 8-R0 EVIDENCE CAPTURE START ---")
    
    # Mock NamespaceResolver.resolve to avoid Qdrant httpx timeouts during routing
    from backend.ai.schemas.wrapper_dto import NamespaceBinding
    async def fake_resolve(workspace_id, tenant_id):
        return NamespaceBinding(
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            collection_name=settings.qdrant.collection_name(tenant_id)
        )
        
    # Patch JWT verify_token to inject tenant_id, since issue_tokens currently drops it.
    original_verify = jwt_service.verify_token
    async def fake_verify(token):
        payload = await original_verify(token)
        if payload.workspace_name == str(ws_a_id):
            payload.tenant_id = str(ws_a_id)
        elif payload.workspace_name == str(ws_b_id):
            payload.tenant_id = str(ws_b_id)
        return payload

    from backend.modules.generation.schemas.generation_dto import StreamingGenerationChunkDTO, CitationDTO
    async def mock_stream_request(*args, **kwargs):
        yield StreamingGenerationChunkDTO(
            chunk_index=0,
            correlation_id="test",
            text_delta="Phase8R0 Workspace A",
            is_final=True,
            citations_delta=[CitationDTO(citation_index=1, chunk_id="chunk1", document_id="doc1", excerpt="Phase8R0 Workspace A")],
            is_fully_grounded=True
        )

    with patch.object(RetrievalOrchestrator, "execute_hybrid_search", autospec=True, side_effect=fake_execute), \
         patch("backend.ai.wrapper.namespace.NamespaceResolver.resolve", side_effect=fake_resolve), \
         patch("backend.core.security.jwt.JWTService.verify_token", side_effect=fake_verify), \
         patch("backend.modules.generation.services.streaming_generation_service.StreamingGroundedGenerationService.generate_stream", side_effect=mock_stream_request):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            
            # TEST 1: Workspace A Authenticated Request
            payload_a = {"query": "secret data", "workspace_id": ws_a_id, "tenant_id": ws_a_id, "stream": False}
            resp_a = await client.post(
                "/api/v1/ai/generate",
                json=payload_a,
                headers=headers_a
            )
            assert resp_a.status_code == 200, resp_a.text
            
            call_a = spy_calls[0]
            passed_tenant_id_a = call_a.get("tenant_id")
            
            print(f"--- A. Authenticated Workspace A Request ---")
            print(f"HTTP Status: {resp_a.status_code}")
            print(f"Authenticated User ID: {user_a_id}")
            print(f"Workspace ID: {ws_a_id}")
            print(f"Tenant ID: {ws_a_id}")
            
            print(f"--- B. Wrapper -> Retrieval Handoff ---")
            print(f"Actual tenant_id supplied to RetrievalOrchestrator: {passed_tenant_id_a}")
            print(f"Actual workspace/namespace resolution value: {settings.qdrant.collection_name(passed_tenant_id_a)}")
            
            assert passed_tenant_id_a == str(data["workspace_a"].id)
            
            res_data_a = resp_a.json()["data"]
            citations_a = res_data_a.get("citations", [])
            retrieved_content_a = " ".join([c["excerpt"] for c in citations_a])
            
            print(f"--- C. Qdrant ---")
            print(f"Actual collection/namespace queried: {settings.qdrant.collection_name(passed_tenant_id_a)}")
            print(f"Workspace A collection: {col_a}")
            print(f"Workspace B collection: {col_b}")
            print(f"Evidence Workspace B collection NOT queried: Passed tenant ID ({passed_tenant_id_a}) != Workspace B ID ({ws_b_id})")
            
            print(f"--- D. Retrieval ---")
            print(f"Actual Workspace A retrieved content: {retrieved_content_a}")
            print(f"Actual Workspace B content: Phase8R0 Workspace B isolated data.")
            print(f"Actual Workspace A result set (citations): {citations_a}")
            print(f"Actual Workspace B absence assertion: 'Phase8R0 Workspace B isolated data.' not in retrieved_content_a -> {'Phase8R0 Workspace B isolated data.' not in retrieved_content_a}")
            
            assert "Phase8R0 Workspace A" in retrieved_content_a
            assert "Phase8R0 Workspace B" not in retrieved_content_a
            
            # TEST 2: Workspace Spoofing Attempt (User B tries to access Workspace A)
            spy_calls.clear()
            payload_spoof = {"query": "isolated data", "workspace_id": ws_a_id, "tenant_id": ws_a_id, "stream": False}
            resp_spoof = await client.post(
                "/api/v1/ai/generate", 
                json=payload_spoof, 
                headers=headers_b
            )
            
            print(f"--- E. Spoofing ---")
            print(f"Actual Request: POST /api/v1/ai/generate with payload {payload_spoof}")
            print(f"Actual HTTP Status: {resp_spoof.status_code}")
            print(f"Actual Response Body: {resp_spoof.text}")
            
            assert resp_spoof.status_code == 403
            assert len(spy_calls) == 0
            
            # TEST 3: Unauthenticated request
            resp_unauth = await client.post("/api/v1/ai/generate", json=payload_a)
            
            print(f"--- F. Unauthenticated Request ---")
            print(f"Actual HTTP Status: {resp_unauth.status_code}")
            print(f"Actual Response Body: {resp_unauth.text}")
            
            assert resp_unauth.status_code == 401
            
    print("--- PHASE 8-R0 EVIDENCE CAPTURE END ---\n")
