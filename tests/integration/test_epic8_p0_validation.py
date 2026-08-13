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
    
    token_a, _, _ = await jwt_service.issue_tokens(user_a)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    # We patch RetrievalOrchestrator to just return empty to prevent deep execution
    from backend.modules.retrieval.schemas.retrieval_dto import RetrievalResultDTO
    async def fake_search(*args, **kwargs):
        return RetrievalResultDTO(
            query="test",
            results=[],
            metadata={}
        )
        
    # We mock NamespaceResolver to avoid Qdrant calls
    from backend.ai.schemas.wrapper_dto import NamespaceBinding
    async def fake_resolve(workspace_id, tenant_id):
        return NamespaceBinding(workspace_id=workspace_id, tenant_id=tenant_id, collection_name="test")

    # We mock the LLM generate_stream to yield one mock chunk to avoid actually calling LLM
    from backend.ai.schemas.wrapper_dto import AIWrapperStreamChunk
    async def mock_stream_request(*args, **kwargs):
        yield AIWrapperStreamChunk(
            correlation_id="test",
            chunk_index=0,
            content="Mock generation complete.",
            is_final=True,
            citations=[],
            is_fully_grounded=True
        )

    # Note: we are NOT mocking AIWrapperService.stream_request here.
    # We want it to execute up to line 146 where it calls execute_hybrid_search with the DTO.
    mocker.patch("backend.modules.retrieval.services.retrieval_service.RetrievalOrchestrator.execute_hybrid_search", side_effect=fake_search)
    mocker.patch("backend.ai.wrapper.namespace.NamespaceResolver.resolve", side_effect=fake_resolve)
    
    # We mock the StreamingGroundedGenerationService inside it
    from backend.modules.generation.services.streaming_generation_service import StreamingGroundedGenerationService
    mocker.patch.object(StreamingGroundedGenerationService, "generate_stream", side_effect=mock_stream_request)
    
    payload = {
        "query": "Hello",
        "workspace_id": ws_a_id,
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # If ValidationError is raised on SearchRequestDTO, it will return 500 or 422.
        resp = await client.post(
            "/api/v1/ai/generate",
            json=payload,
            headers=headers_a
        )
        assert resp.status_code == 200, resp.text
