import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.core.security.jwt import get_jwt_service
from unittest.mock import patch

@pytest.mark.asyncio
async def test_epic8_p0_search_request_dto_validation(isolation_test_data, mocker):
    """
    Proves that the AIWrapperService constructs a valid SearchRequestDTO
    without raising pydantic.ValidationError for non-existent fields like 'rerank'.
    """
    data = isolation_test_data
    jwt_service = get_jwt_service()

    user_a = data["user_a"]
    ws_a = data["workspace_a"]
    ws_a_id = str(ws_a.id)

    from backend.core.dependencies.database import get_db
    from backend.document.models.document import Document
    from backend.document.models.status import DocumentStatus

    token_a, _, _ = await jwt_service.issue_tokens(user_a)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    async_session_gen = get_db()
    db = await async_session_gen.__anext__()
    try:
        doc_a = Document(
            tenant_id=ws_a_id, owner_user_id=uuid.UUID(str(user_a.id)),
            filename="doc_a.txt", original_filename="doc_a.txt", status=DocumentStatus.READY
        )
        db.add(doc_a)
        await db.commit()
    finally:
        await db.close()

    # We patch RetrievalOrchestrator to just return empty to prevent deep execution
    from backend.modules.retrieval.schemas.retrieval_dto import RetrievalResultDTOv2
    async def fake_search(*args, **kwargs):
        return RetrievalResultDTOv2(
            query_text="test",
            tenant_id=ws_a_id,
            correlation_id="test",
            top_k_requested=5,
            dense_candidates_count=0,
            sparse_candidates_count=0,
            unique_candidates_merged=0,
            final_evidence=[],
            stage_latencies={}
        )

    # We mock NamespaceResolver to avoid Qdrant calls
    from backend.ai.schemas.wrapper_dto import NamespaceBinding
    async def fake_resolve(workspace_id, tenant_id):
        return NamespaceBinding(workspace_id=workspace_id, tenant_id=tenant_id, collection_name="test")

    from backend.modules.generation.schemas.generation_dto import StreamingGenerationChunkDTO
    async def mock_stream_request(*args, **kwargs):
        yield StreamingGenerationChunkDTO(
            chunk_index=0,
            correlation_id="test",
            text_delta="Mock generation complete.",
            is_final=True,
            citations_delta=[],
            is_fully_grounded=True
        )

    # Note: we are NOT mocking AIWrapperService.stream_request here.
    # We want it to execute up to line 146 where it calls execute_hybrid_search with the DTO.
    # Patch JWT verify_token to inject tenant_id, since issue_tokens currently drops it.
    original_verify = jwt_service.verify_token
    async def fake_verify(token):
        payload = await original_verify(token)
        if payload.workspace_name == str(ws_a_id):
            payload.tenant_id = str(ws_a_id)
        return payload

    mocker.patch("backend.core.security.jwt.JWTService.verify_token", side_effect=fake_verify)
    mocker.patch("backend.modules.retrieval.services.retrieval_service.RetrievalOrchestrator.execute_hybrid_search", side_effect=fake_search)
    mocker.patch("backend.ai.wrapper.namespace.NamespaceResolver.resolve", side_effect=fake_resolve)

    # We mock the StreamingGroundedGenerationService inside it
    from backend.modules.generation.services.streaming_generation_service import StreamingGroundedGenerationService
    mocker.patch.object(StreamingGroundedGenerationService, "generate_stream", side_effect=mock_stream_request)

    payload = {
        "query": "Hello",
        "workspace_id": ws_a_id,
        "tenant_id": ws_a_id,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # If ValidationError is raised on SearchRequestDTO, it will return 500 or 422.
        resp = await client.post(
            "/api/v1/ai/generate",
            json=payload,
            headers=headers_a
        )
        assert resp.status_code == 200, resp.text
