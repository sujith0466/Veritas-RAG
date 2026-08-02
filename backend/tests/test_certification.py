"""Certification Integration Tests.

End-to-end tests validating RBAC, Tenant Isolation, Chat features,
and the real RAG pipeline for the RAGuard v1.0 certification.
"""

import os

import httpx
import pytest

API_URL = "http://127.0.0.1:8000"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

@pytest.fixture
async def async_client():
    async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as client:
        yield client

@pytest.fixture
async def supa_client():
    async with httpx.AsyncClient() as client:
        yield client

async def get_token(client: httpx.AsyncClient, email: str, password: str = "ChangeMe123!") -> str:
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }
    resp = await client.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers=headers,
        json={"email": email, "password": password}
    )
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()["access_token"]


async def create_user_if_not_exists(client: httpx.AsyncClient, email: str, role: str, tenant_id: str):
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    resp = await client.get(f"{SUPABASE_URL}/auth/v1/admin/users", headers=headers)
    assert resp.status_code == 200
    users = resp.json().get("users", [])
    if not any(u.get("email") == email for u in users):
        create_payload = {
            "email": email,
            "password": "ChangeMe123!",
            "email_confirm": True,
            "user_metadata": {"role": role, "tenant_id": tenant_id}
        }
        await client.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=headers,
            json=create_payload
        )


@pytest.fixture
async def tokens(supa_client: httpx.AsyncClient):
    # Ensure a second tenant exists for tenant isolation tests
    await create_user_if_not_exists(supa_client, "demo2@gmail.com", "viewer", "demo-tenant-2")

    return {
        "admin": await get_token(supa_client, "demoadmin@gmail.com"),
        "user": await get_token(supa_client, "demo@gmail.com"),
        "user2": await get_token(supa_client, "demo2@gmail.com"),
    }


@pytest.mark.anyio
async def test_auth_and_rbac(async_client: httpx.AsyncClient, tokens: dict):
    # 1. Admin accessing diagnostics
    resp = await async_client.get("/api/v1/health/detailed", headers={"Authorization": f"Bearer {tokens['admin']}"})
    assert resp.status_code == 200, "Admin should access diagnostics"

    # 2. User accessing diagnostics (should be 403 Forbidden)
    resp = await async_client.get("/api/v1/health/detailed", headers={"Authorization": f"Bearer {tokens['user']}"})
    assert resp.status_code == 403, f"User should be forbidden, got {resp.status_code}"


@pytest.mark.anyio
async def test_tenant_isolation(async_client: httpx.AsyncClient, tokens: dict):
    # 1. Admin gets their documents
    resp1 = await async_client.get("/api/v1/documents", headers={"Authorization": f"Bearer {tokens['admin']}"})
    assert resp1.status_code == 200
    docs1 = resp1.json()["data"]["items"]
    assert len(docs1) > 0, "Admin should have the seeded documents"

    # 2. User in Tenant 2 gets their documents
    resp2 = await async_client.get("/api/v1/documents", headers={"Authorization": f"Bearer {tokens['user2']}"})
    assert resp2.status_code == 200
    docs2 = resp2.json()["data"]["items"]
    assert len(docs2) == 0, "User in Tenant 2 should not see Tenant 1 documents"


@pytest.mark.anyio
async def test_chat_lifecycle(async_client: httpx.AsyncClient, tokens: dict):
    headers = {"Authorization": f"Bearer {tokens['user']}"}

    # 1. Create conversation
    resp = await async_client.post("/api/v1/chat/sessions", headers=headers, json={"title": "Test Chat"})
    assert resp.status_code in (200, 201)
    session_id = resp.json()["data"]["id"]

    # 2. Rename conversation
    resp = await async_client.put(f"/api/v1/chat/sessions/{session_id}", headers=headers, json={"title": "Renamed Chat"})
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "Renamed Chat"

    # 3. Pin conversation
    resp = await async_client.put(f"/api/v1/chat/sessions/{session_id}", headers=headers, json={"pinned": True})
    assert resp.status_code == 200
    assert resp.json()["data"]["pinned"] is True

    # 4. Persistence after refresh (List conversations)
    resp = await async_client.get("/api/v1/chat/sessions", headers=headers)
    assert resp.status_code == 200
    sessions = resp.json()["data"]
    assert any(s["id"] == session_id for s in sessions), "Chat session should persist"

    # 5. Delete conversation
    resp = await async_client.delete(f"/api/v1/chat/sessions/{session_id}", headers=headers)
    assert resp.status_code == 204


@pytest.mark.anyio
async def test_rag_pipeline_retrieval(async_client: httpx.AsyncClient, tokens: dict):
    headers = {"Authorization": f"Bearer {tokens['admin']}"}

    # Use real RAG pipeline (this depends on the seeded documents from demo_bootstrap.py)
    # The HR policy document contains: "Full-time employees accrue 15 days of PTO per year."

    # 1. Create a session
    resp = await async_client.post("/api/v1/chat/sessions", headers=headers, json={"title": "PTO Question"})
    assert resp.status_code in (200, 201)
    session_id = resp.json()["data"]["id"]

    # 2. Send message
    resp = await async_client.post(
        f"/api/v1/chat/sessions/{session_id}/stream",
        headers=headers,
        json={"query": "How many days of PTO do I get?"}
    )
    assert resp.status_code == 200
    text_data = resp.text

    # 3. Verify Grounded Generation and Citations
    assert "15 days" in text_data.lower(), "AI should use grounded knowledge (15 days of PTO)"

    # Verify citations were returned
    assert "citations" in text_data.lower(), "AI should potentially return citations"
