import pytest
import uuid
import asyncio
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.core.security.jwt import get_jwt_service

@pytest.mark.asyncio
async def test_epic8_p0_chat_orchestrator_ws_name_error(isolation_test_data, mocker):
    """
    Proves that calling stream_chat without providing a workspace_id does not 
    crash with a NameError on 'ws' when resolving the active workspace.
    """
    data = isolation_test_data
    jwt_service = get_jwt_service()
    
    user_a = data["user_a"]
    ws_a = data["workspace_a"]
    
    token_a, _, _ = await jwt_service.issue_tokens(user_a)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    original_verify = jwt_service.verify_token
    async def fake_verify(token):
        payload = await original_verify(token)
        if payload.workspace_name == str(ws_a.id):
            payload.tenant_id = str(ws_a.id)
        return payload

    mocker.patch("backend.core.security.jwt.JWTService.verify_token", side_effect=fake_verify)
    
    # Payload WITHOUT workspace_id to trigger line 142 in chat_orchestrator.py
    payload = {
        "query": "Hello without workspace_id",
        # "workspace_id": ... # intentionally omitted
    }
    
    # We mock out AIWrapperService.stream_request to avoid testing the LLM logic here
    async def mock_stream_request(self, request, user_id, correlation_id):
        from backend.ai.schemas.wrapper_dto import AIWrapperStreamChunk
        yield AIWrapperStreamChunk(
            correlation_id=correlation_id,
            chunk_index=0,
            content="Mocked stream.",
            is_final=True,
            citations=[],
            is_fully_grounded=True
        )

    mocker.patch("backend.ai.wrapper.service.AIWrapperService.stream_request", new=mock_stream_request)

    session_id = str(uuid.uuid4())
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Request should not crash with 500 (NameError).
        resp = await client.post(
            f"/api/v1/chat/sessions/{session_id}/stream",
            json=payload,
            headers=headers_a
        )
        
        # If the NameError occurred, this would be a 500.
        assert resp.status_code == 200, resp.text
        
        content = ""
        async for chunk in resp.aiter_text():
            content += chunk
            
        assert "data:" in content
        assert "Chat session not found" in content
