import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.main import app
from backend.core.security.jwt import get_jwt_service
from backend.core.dependencies.database import get_db
from backend.models.entities.identity_provider import IdentityProvider

@pytest.mark.asyncio
async def test_sso_create_idp_success(isolation_test_data):
    data = isolation_test_data
    jwt_service = get_jwt_service()
    
    # Issue token for User A (Owner of Workspace A)
    token_a, _, _ = await jwt_service.issue_tokens(data["user_a"])
    headers = {"Authorization": f"Bearer {token_a}"}

    payload = {
        "name": "Okta",
        "type": "saml",
        "entity_id_issuer": "https://okta.example.com",
        "sso_url": "https://okta.example.com/sso",
        "attribute_mapping": {"email": "email"}
    }
    
    async_session_gen = get_db()
    db = await async_session_gen.__anext__()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"/api/v1/workspaces/{data['workspace_a'].slug}/idp", json=payload, headers=headers)
            assert resp.status_code == 201
            
            # Verify it uses the real workspace_id
            idp_id = resp.json()["id"]
            stmt = select(IdentityProvider).where(IdentityProvider.id == idp_id)
            idp = await db.scalar(stmt)
            assert str(idp.workspace_id) == str(data["workspace_a"].id)
    finally:
        await db.close()

@pytest.mark.asyncio
async def test_sso_create_idp_unauthorized_user(isolation_test_data):
    data = isolation_test_data
    jwt_service = get_jwt_service()
    
    # User B trying to create IDP in Workspace A
    token_b, _, _ = await jwt_service.issue_tokens(data["user_b"])
    headers = {"Authorization": f"Bearer {token_b}"}

    payload = {
        "name": "Okta",
        "type": "saml",
        "entity_id_issuer": "https://okta.example.com",
        "sso_url": "https://okta.example.com/sso",
        "attribute_mapping": {"email": "email"}
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/api/v1/workspaces/{data['workspace_a'].slug}/idp", json=payload, headers=headers)
        # Assuming HTTP 403 because they are not a member of Workspace A
        assert resp.status_code == 403

@pytest.mark.asyncio
async def test_sso_create_idp_unknown_workspace(isolation_test_data):
    data = isolation_test_data
    jwt_service = get_jwt_service()
    
    token_a, _, _ = await jwt_service.issue_tokens(data["user_a"])
    headers = {"Authorization": f"Bearer {token_a}"}

    payload = {
        "name": "Okta",
        "type": "saml",
        "entity_id_issuer": "https://okta.example.com",
        "sso_url": "https://okta.example.com/sso",
        "attribute_mapping": {"email": "email"}
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/api/v1/workspaces/unknown-slug/idp", json=payload, headers=headers)
        assert resp.status_code == 404

@pytest.mark.asyncio
async def test_sso_create_idp_unauthenticated():
    payload = {
        "name": "Okta",
        "type": "saml",
        "entity_id_issuer": "https://okta.example.com",
        "sso_url": "https://okta.example.com/sso",
        "attribute_mapping": {"email": "email"}
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/api/v1/workspaces/any-slug/idp", json=payload)
        assert resp.status_code == 401
