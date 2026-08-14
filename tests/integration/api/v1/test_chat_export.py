import json
import pytest
from httpx import AsyncClient
from backend.models.entities.user import User
from backend.core.permissions.rbac import Role
from backend.modules.chat.models import ChatSession, ChatMessage
import uuid
from datetime import datetime, UTC, timedelta

@pytest.fixture
async def sample_chat_data(db_session, workspace, owner_user):
    session_id = str(uuid.uuid4())
    chat_session = ChatSession(
        id=session_id,
        tenant_id=workspace.id,
        user_id=owner_user.id,
        title="Test Export Session"
    )
    db_session.add(chat_session)
    
    msg_id = str(uuid.uuid4())
    chat_msg = ChatMessage(
        id=msg_id,
        session_id=session_id,
        role="user",
        message="Hello AI",
        created_at=datetime.now(UTC)
    )
    db_session.add(chat_msg)
    await db_session.commit()
    
    return chat_session, chat_msg

@pytest.mark.asyncio
async def test_owner_can_export_json(async_client: AsyncClient, owner_headers: dict, workspace, sample_chat_data):
    response = await async_client.get(
        f"/api/v1/workspaces/{workspace.id}/chat/export?format=json",
        headers=owner_headers
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    
    data = response.json()
    assert len(data) >= 1
    assert data[0]["message"] == "Hello AI"
    assert data[0]["role"] == "user"
    assert data[0]["session_title"] == "Test Export Session"

@pytest.mark.asyncio
async def test_owner_can_export_csv(async_client: AsyncClient, owner_headers: dict, workspace, sample_chat_data):
    response = await async_client.get(
        f"/api/v1/workspaces/{workspace.id}/chat/export?format=csv",
        headers=owner_headers
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "Hello AI" in response.text
    assert "Test Export Session" in response.text

@pytest.mark.asyncio
async def test_member_cannot_export(async_client: AsyncClient, member_headers: dict, workspace, sample_chat_data):
    response = await async_client.get(
        f"/api/v1/workspaces/{workspace.id}/chat/export?format=json",
        headers=member_headers
    )
    assert response.status_code == 403

@pytest.mark.asyncio
async def test_cross_workspace_export_denied(async_client: AsyncClient, owner_headers: dict):
    fake_workspace_id = str(uuid.uuid4())
    response = await async_client.get(
        f"/api/v1/workspaces/{fake_workspace_id}/chat/export?format=json",
        headers=owner_headers
    )
    assert response.status_code == 403
