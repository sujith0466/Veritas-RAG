import pytest
import uuid
import time
import httpx
from backend.ai.providers.v1_engine.client import V1EngineClient
from backend.ai.schemas.wrapper_dto import AIWrapperRequest
from backend.core.config import get_settings

@pytest.mark.asyncio
async def test_epic8_r2_contract_hmac():
    settings = get_settings().v1_engine
    settings.signing_key = "test-signing-key"
    
    body = b'{"test": "payload"}'
    ts = 1600000000
    
    signature = V1EngineClient._sign_request("POST", "/v1/generate/stream", body, ts)
    assert signature != ""
    assert isinstance(signature, str)

@pytest.mark.asyncio
async def test_epic8_r2_contract_stream_dto():
    req = AIWrapperRequest(
        workspace_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        query="test query",
        stream=True
    )
    assert req.query == "test query"
