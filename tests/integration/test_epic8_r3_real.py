print("STARTING SCRIPT")
import asyncio
import os
import sys
import time
import subprocess
import json

CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(CWD, "..", "..")))

os.environ["V1_ENGINE_ENABLED"] = "true"
os.environ["V1_ENGINE_BASE_URL"] = "https://localhost:8443"
os.environ["V1_ENGINE_SIGNING_KEY"] = "test-signing-key"
os.environ["V1_ENGINE_CA_CERT_PATH"] = os.path.join(CWD, "test_ca.crt")
os.environ["V1_ENGINE_CLIENT_CERT_PATH"] = os.path.join(CWD, "test_client.crt")
os.environ["V1_ENGINE_CLIENT_KEY_PATH"] = os.path.join(CWD, "test_client.key")
os.environ["LLM_PROVIDER_PRIORITY"] = "v1_engine,openrouter,gemini"
os.environ["ENABLE_SSE_RECOVERY"] = "true"

from backend.database.engine import get_session_factory, get_engine
from backend.models.base import BaseModel
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.models.entities.workspace_member import WorkspaceMember, WorkspaceRole
from backend.modules.chat.models.chat_message import ChatMessage
from backend.cache.client import get_redis_client, close_cache
from backend.core.config import get_settings
from backend.modules.chat.services.chat_orchestrator import ChatOrchestrator
from backend.ai.providers.v1_engine.client import V1EngineClient
from backend.ai.wrapper.service import AIWrapperService
from sqlalchemy import select

import pytest

async def setup_test_db():
    factory = get_session_factory()
    async with factory() as session:
        import uuid
        workspace_id = uuid.uuid4()
        tenant_id = workspace_id  # In this system, they must match for the validation check
        user_id = uuid.uuid4()
        
        user = User(id=str(user_id), email=f"test-{user_id.hex[:8]}@example.com", role="viewer")
        workspace = Workspace(id=str(workspace_id), name="Test Workspace", slug=f"test-ws-{workspace_id.hex[:6]}", storage_prefix=f"test-{workspace_id.hex[:6]}", qdrant_namespace=f"test-{workspace_id.hex[:6]}", status="ACTIVE")
        member = WorkspaceMember(workspace_id=str(workspace_id), user_id=str(user_id), role=WorkspaceRole.OWNER.value)
        settings = WorkspaceSettings(workspace_id=str(workspace_id), settings_json={"ai_enabled": True})
        
        from backend.document.models.document import Document
        from backend.document.models.status import DocumentStatus
        doc = Document(id=str(uuid.uuid4()), tenant_id=str(tenant_id), filename="test.pdf", original_filename="test.pdf", status=DocumentStatus.READY)
        
        from backend.modules.chat.models import ChatSession
        session_id = uuid.uuid4()
        chat_session = ChatSession(id=str(session_id), tenant_id=str(tenant_id), user_id=str(user_id), title="Test Session")
        
        session.add_all([user, workspace, member, settings, doc, chat_session])
        await session.commit()
        
        return str(tenant_id), str(workspace_id), str(user_id), str(session_id)

async def run_r3_real_verification():
    print("============================================================")
    print("PHASE 8-R3: REAL INFRASTRUCTURE VERIFICATION")
    print("============================================================")
    
    print("\n[A] Initializing Real Postgres & Redis...")
    tenant_id, workspace_id, user_id, session_id = await setup_test_db()
    redis = get_redis_client()
    # clean redis
    await redis.flushdb()
    
    print("\n[B] Starting Sandbox Server with mTLS...")
    cmd = [
        sys.executable, "-m", "uvicorn", "sandbox_v1_server:app",
        "--host", "localhost", "--port", "8443",
        "--ssl-keyfile", "test_server.key",
        "--ssl-certfile", "test_server.crt",
        "--ssl-ca-certs", "test_ca.crt",
        "--ssl-cert-reqs", "2"
    ]
    server_proc = subprocess.Popen(cmd, cwd=CWD, stdout=sys.stdout, stderr=sys.stderr)
    await asyncio.sleep(2.0)
    
    get_settings.cache_clear()
    settings = get_settings()
    
    await V1EngineClient.initialize()
    
    from backend.modules.chat.repositories.chat_repository import ChatRepository
    from backend.ai.manager import LLMProviderManager
    from backend.modules.generation.services.streaming_generation_service import StreamingGroundedGenerationService
    from backend.modules.generation.services.citation_extractor import CitationExtractor
    from unittest.mock import AsyncMock
    
    factory = get_session_factory()
    session = factory()
    chat_repo = ChatRepository(session=session)
    
    llm = LLMProviderManager()
    wrapper_svc = AIWrapperService(
        namespace_resolver=AsyncMock(),
        rate_limiter=AsyncMock(),
        retrieval_orchestrator=AsyncMock(),
        streaming_generation=StreamingGroundedGenerationService(citation_extractor=CitationExtractor(), llm_provider=llm),
        event_dispatcher=AsyncMock(),
        llm_manager=llm
    )
    
    orchestrator = ChatOrchestrator(chat_repo=chat_repo, ai_wrapper_service=wrapper_svc)
    
    try:
        import uuid
        correlation_id = "req_" + uuid.uuid4().hex[:8]
        
        print("\n--- EP8-016: Recovery Configuration ---")
        print(f"ENABLE_SSE_RECOVERY: {settings.features.enable_sse_recovery}")
        
        print("\n--- EP8-014: Explicit Terminal Done Event ---")
        generator = orchestrator.stream_chat(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            session_id=session_id,
            user_id=user_id,
            query="Hello",
            correlation_id=correlation_id
        )
        
        chunks = []
        async for sse in generator:
            chunks.append(sse)
            print(sse.strip())
            
        print("SUCCESS: Stream completed.")
        
        print("\n--- EP8-018: Real Redis Buffer & TTL ---")
        redis_key = f"raguard:{tenant_id}:sse:{correlation_id}"
        ttl = await redis.ttl(redis_key)
        count = await redis.llen(redis_key)
        print(f"Redis Key: {redis_key} | TTL: {ttl} | Count: {count}")
        assert ttl > 0
        assert count > 0
        
        print("\n--- EP8-015: Last-Event-ID Validation ---")
        print("Test Valid:")
        replay_gen = orchestrator.stream_chat(
            tenant_id=tenant_id, workspace_id=workspace_id, session_id=session_id,
            user_id=user_id, query="Hello", correlation_id=correlation_id,
            last_event_id=f"{correlation_id}:0"
        )
        async for sse in replay_gen:
            print(sse.strip())
            
        print("\nTest Invalid:")
        bad_gen = orchestrator.stream_chat(
            tenant_id=tenant_id, workspace_id=workspace_id, session_id=session_id,
            user_id=user_id, query="Hello", correlation_id=correlation_id,
            last_event_id="bad_id:0"
        )
        async for sse in bad_gen:
            print(sse.strip())
            
        print("\n--- EP8-019 & EP8-020: TTFT Timeout ---")
        to_corr = f"req_{uuid.uuid4().hex[:8]}"
        to_sess = str(uuid.uuid4())
        to_gen = orchestrator.stream_chat(
            tenant_id=tenant_id, workspace_id=workspace_id, session_id=to_sess,
            user_id=user_id, query="TIMEOUT_MODE", correlation_id=to_corr
        )
        async for sse in to_gen:
            print(sse.strip())
            
        print("\n--- EP8-024: Empty Persistence Prevention ---")
        # Check DB for to_sess
        factory = get_session_factory()
        async with factory() as session:
            msgs = (await session.execute(select(ChatMessage).where(ChatMessage.session_id == to_sess))).scalars().all()
            print(f"Messages for timed out session (empty): {len(msgs)}")
            for m in msgs:
                print(f"  {m.role}: {m.message}")
            assert len(msgs) == 1 # Only user msg
            
        print("\n--- EP8-021 & EP8-022 & EP8-023: Cancellation & Partial Persistence & Upstream Close ---")
        hang_corr = f"req_{uuid.uuid4().hex[:8]}"
        hang_sess = str(uuid.uuid4())
        hang_gen = orchestrator.stream_chat(
            tenant_id=tenant_id, workspace_id=workspace_id, session_id=hang_sess,
            user_id=user_id, query="HANG_MODE", correlation_id=hang_corr
        )
        
        idx = 0
        try:
            async for sse in hang_gen:
                print(sse.strip())
                if idx == 0:
                    print("Client disconnect detected. Cancelling...")
                    await hang_gen.aclose()
                    break
                idx += 1
        except asyncio.CancelledError:
            print("CancelledError successfully handled!")
            
        # Give background tasks time to execute
        await asyncio.sleep(1.0)
        
        print("\nChecking DB for partial persistence...")
        async with factory() as session:
            msgs = (await session.execute(select(ChatMessage).where(ChatMessage.session_id == hang_sess))).scalars().all()
            print(f"Messages for cancelled session: {len(msgs)}")
            for m in msgs:
                print(f"  {m.role}: {m.message}")
                
        print("\n--- Closing and cleaning up ---")
    finally:
        await V1EngineClient.close()
        server_proc.kill()
        server_proc.wait()
        await close_cache()
        # Give extra time for any lingering unawaited tasks
        await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(run_r3_real_verification())


