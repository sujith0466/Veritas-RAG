import asyncio
import os
import signal
import subprocess
import time
import pytest
import httpx
import uuid
from backend.core.config import get_settings
from backend.ai.manager import LLMProviderManager
from backend.ai.interfaces.llm_provider import LLMRequest
from backend.ai.providers.v1_engine.client import V1EngineClient
from backend.ai.providers.v1_engine.provider import V1EngineProvider
from backend.ai.wrapper.service import AIWrapperService, WorkspaceValidationError
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.database.engine import get_session_factory
from backend.core.exceptions import LLMProviderException

@pytest.fixture(scope="module")
def sandbox_server():
    # Start the FastAPI server using Uvicorn with mTLS in a subprocess
    cwd = os.path.dirname(__file__)
    cmd = [
        "python", "-m", "uvicorn", "sandbox_v1_server:app",
        "--host", "localhost", "--port", "8443",
        "--ssl-keyfile", "test_server.key",
        "--ssl-certfile", "test_server.crt",
        "--ssl-ca-certs", "test_ca.crt",
        "--ssl-cert-reqs", "2"
    ]
    process = subprocess.Popen(cmd, cwd=cwd)
    
    # Wait for server to start
    time.sleep(2)
    
    yield
    
    # Teardown
    process.terminate()
    process.wait()

@pytest.mark.asyncio
async def test_r2_real_provider_integration(sandbox_server, monkeypatch):
    monkeypatch.setenv("V1_ENGINE_ENABLED", "true")
    monkeypatch.setenv("V1_ENGINE_BASE_URL", "https://localhost:8443")
    monkeypatch.setenv("V1_ENGINE_SIGNING_KEY", "test-signing-key")
    monkeypatch.setenv("V1_ENGINE_CA_CERT_PATH", os.path.join(os.path.dirname(__file__), "test_ca.crt"))
    monkeypatch.setenv("V1_ENGINE_CLIENT_CERT_PATH", os.path.join(os.path.dirname(__file__), "test_client.crt"))
    monkeypatch.setenv("V1_ENGINE_CLIENT_KEY_PATH", os.path.join(os.path.dirname(__file__), "test_client.key"))
    monkeypatch.setenv("LLM_PROVIDER_PRIORITY", "v1_engine,openrouter,gemini")
    
    # Need to clear cache to pick up env vars
    from backend.core.config import get_settings
    get_settings.cache_clear()
    settings = get_settings()
    
    # Re-initialize client
    await V1EngineClient.close()
    await V1EngineClient.initialize()
    
    # 1. Health Cache Evidence
    provider = V1EngineProvider()
    is_healthy = await provider.health_check()
    assert is_healthy is True
    
    # 2. Test Stream via LLMProviderManager
    manager = LLMProviderManager()
    req = LLMRequest(
        prompt="hello",
        tenant_id=str(uuid.uuid4()),
        workspace_id=str(uuid.uuid4())
    )
    
    chunks = []
    async for chunk in manager.stream(req):
        chunks.append(chunk)
        
    full_text = "".join(chunks)
    assert "Real Sandbox V1 response chunk 1." in full_text
    
    # 3. Test Negative Control (Mock Fallback shouldn't run when server is down)
    monkeypatch.setenv("V1_ENGINE_BASE_URL", "https://localhost:8444")
    monkeypatch.setenv("LLM_PROVIDER_PRIORITY", "v1_engine")
    get_settings.cache_clear()
    await V1EngineClient.close()
    
    # We expect initialize to fail or stream to fail, but stream is where it gets caught by LLMProviderException
    try:
        await V1EngineClient.initialize()
    except Exception:
        pass # Client init might fail if version check fails, which is fine
        
    # Get a fresh manager that reads the updated settings
    manager = LLMProviderManager()
        
    with pytest.raises(LLMProviderException):
        async for _ in manager.stream(req):
            pass

@pytest.mark.asyncio
async def test_r2_ai_enabled_flag(setup_database):
    # EP8-006 test
    # Create workspace with AI disabled
    from backend.ai.schemas.wrapper_dto import AIWrapperRequest
    from backend.ai.wrapper.service import WorkspaceValidationError
    from unittest.mock import Mock
    from backend.database.engine import get_session_factory
    
    factory = get_session_factory()
    async with factory() as db_session:
        ws_id = uuid.uuid4()
        t_id = uuid.uuid4()
        ws = Workspace(id=t_id, name="Test WS", slug="test-ws-x", storage_prefix="p-x", qdrant_namespace="q-x", status="ACTIVE")
        db_session.add(ws)
        ws_settings = WorkspaceSettings(workspace_id=t_id, settings_json={"ai_enabled": False})
        db_session.add(ws_settings)
        await db_session.commit()
    
    req = AIWrapperRequest(workspace_id=t_id, tenant_id=t_id, query="hello", stream=False)
    
    service = AIWrapperService(
        namespace_resolver=Mock(),
        rate_limiter=Mock(),
        retrieval_orchestrator=Mock(),
        streaming_generation=Mock(),
        event_dispatcher=Mock(),
        llm_manager=Mock()
    )
    
    with pytest.raises(WorkspaceValidationError) as exc:
        await service._validate_workspace(req, uuid.uuid4())
    
    assert "AI features disabled" in str(exc.value)

