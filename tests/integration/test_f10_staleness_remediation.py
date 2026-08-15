import pytest
from httpx import AsyncClient, ASGITransport
import uuid
from datetime import datetime, timedelta

from backend.main import app
from backend.database.engine import get_session_factory
from backend.modules.knowledge_base.schemas.staleness_dto import StalenessPolicyDTO
from backend.modules.knowledge_base.services.staleness_service import StalenessService
from backend.modules.knowledge_health.workers.tasks import _async_evaluate_all_workspaces_staleness
from backend.repositories.workspace_settings import WorkspaceSettingsRepository
from backend.repositories.workspace_settings_history import WorkspaceSettingsHistoryRepository
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.services.workspace.settings_service import WorkspaceSettingsService
from backend.document.models import Document
from backend.core.events.dispatcher import EventDispatcher

@pytest.mark.asyncio
async def test_staleness_policy_remediation(app, isolation_test_data):
    from backend.core.security.jwt import get_jwt_service
    data = isolation_test_data
    jwt_service = get_jwt_service()
    
    token_a, _, _ = await jwt_service.issue_tokens(data["user_a"])
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    ws_a = data["workspace_a"]
    ws_b = data["workspace_b"]
    
    factory = get_session_factory()
    
    # 1. Create test documents
    from datetime import timezone
    async with factory() as session:
        # Document for Workspace A: age = 60 days
        doc_a = Document(
            tenant_id=str(ws_a.id),
            filename="doc_a.pdf",
            original_filename="doc_a.pdf",
            relative_path="test/doc_a.pdf",
            status="READY",
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
            updated_at=datetime.now(timezone.utc) - timedelta(days=60)
        )
        # Document for Workspace B: age = 60 days
        doc_b = Document(
            tenant_id=str(ws_b.id),
            filename="doc_b.pdf",
            original_filename="doc_b.pdf",
            relative_path="test/doc_b.pdf",
            status="READY",
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
            updated_at=datetime.now(timezone.utc) - timedelta(days=60)
        )
        session.add_all([doc_a, doc_b])
        await session.commit()
    
    # 2. Phase 2A: Policy Persistence & Phase 2F: Authorization
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        url_ws_a = f"/api/v1/workspaces/{ws_a.id}/knowledge-base/staleness/policy"
        
        policy_a = StalenessPolicyDTO(
            inactivity_threshold_days=30, # Should be stale at 60 days
            max_age_days=365,
            decay_model="linear",
            auto_stale_flagging=True
        )
        
        req_payload = {
            "expected_updated_at": datetime.now(timezone.utc).isoformat(),
            "policy": policy_a.model_dump()
        }
        
        # User A setting policy for WS A -> Success
        res = await client.put(url_ws_a, json=req_payload, headers=headers_a)
        assert res.status_code == 200, res.text
        
        # Verify persistence directly via DB
        async with factory() as session:
            settings_service = WorkspaceSettingsService(
                WorkspaceSettingsRepository(session),
                WorkspaceSettingsHistoryRepository(session),
                WorkspaceRepository(session),
                WorkspaceMemberRepository(session)
            )
            settings_a = await settings_service.get_settings(session, ws_a.id, data["user_a"].id)
            assert "staleness" in settings_a.settings_json
            assert settings_a.settings_json["staleness"]["inactivity_threshold_days"] == 30
    
    # User B setting policy for WS B directly using the service for speed
    async with factory() as session:
        settings_service = WorkspaceSettingsService(
            WorkspaceSettingsRepository(session),
            WorkspaceSettingsHistoryRepository(session),
            WorkspaceRepository(session),
            WorkspaceMemberRepository(session)
        )
        settings_b = await settings_service.get_settings(session, ws_b.id, data["user_b"].id)
        
        policy_b = StalenessPolicyDTO(
            inactivity_threshold_days=90, # Should NOT be stale at 60 days
            max_age_days=365,
            decay_model="linear",
            auto_stale_flagging=True
        )
        
        await settings_service.patch_settings(
            session=session,
            workspace_id=ws_b.id,
            user_id=data["user_b"].id,
            expected_updated_at=settings_b.updated_at,
            patch_data={"staleness": policy_b.model_dump()}
        )
        
    # 3. Phase 2B & 2C: Cross-Workspace Policy Isolation and Background worker correctness
    # Reset updated_at since the API call might have modified it
    async with factory() as session:
        from sqlalchemy import update
        await session.execute(update(Document).where(Document.id == doc_a.id).values(updated_at=datetime.now(timezone.utc) - timedelta(days=60)))
        await session.execute(update(Document).where(Document.id == doc_b.id).values(updated_at=datetime.now(timezone.utc) - timedelta(days=60)))
        await session.commit()
        
    # Run the background job
    res = await _async_evaluate_all_workspaces_staleness()
    assert res["workspaces_processed"] >= 2
    
    # 4. Verify results
    async with factory() as session:
        dispatcher = EventDispatcher()
        service = StalenessService(session, dispatcher)
        
        rep_a = await service.get_staleness_report(ws_a.id)
        rep_b = await service.get_staleness_report(ws_b.id)
        
        # Workspace A doc should be stale (60 > 30)
        assert rep_a.total_documents == 1
        assert rep_a.stale_count == 1
        
        # Workspace B doc should NOT be stale (60 < 90)
        assert rep_b.total_documents == 1
        assert rep_b.stale_count == 0
        
    # 5. Phase 2E: Idempotency
    res2 = await _async_evaluate_all_workspaces_staleness()
    assert res2["workspaces_processed"] >= 2
    
    async with factory() as session:
        dispatcher = EventDispatcher()
        service = StalenessService(session, dispatcher)
        
        rep_a2 = await service.get_staleness_report(ws_a.id)
        # Should remain the same, no duplicates
        assert rep_a2.total_documents == 1
        assert rep_a2.stale_count == 1

