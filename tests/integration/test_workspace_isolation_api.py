import pytest
from httpx import AsyncClient, ASGITransport
import uuid

from backend.main import app

@pytest.mark.asyncio
async def test_authorization_matrix(app, isolation_test_data):
    from backend.core.security.jwt import get_jwt_service
    data = isolation_test_data
    jwt_service = get_jwt_service()
    
    token_a, _, _ = await jwt_service.issue_tokens(data["user_a"])
    token_b, _, _ = await jwt_service.issue_tokens(data["user_b"])
    token_c, _, _ = await jwt_service.issue_tokens(data["user_c"])
    
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    headers_c = {"Authorization": f"Bearer {token_c}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        url_ws_a = f"/api/v1/workspaces/{data['workspace_a'].id}/members"
        url_ws_b = f"/api/v1/workspaces/{data['workspace_b'].id}/members"
        
        # 1. User A + Workspace A -> ALLOWED
        res_1 = await client.get(url_ws_a, headers=headers_a)
        assert res_1.status_code == 200

        # 2. User A + Workspace B -> DENIED
        res_2 = await client.get(url_ws_b, headers=headers_a)
        assert res_2.status_code == 403

        # 3. User B + Workspace A -> DENIED
        res_3 = await client.get(url_ws_a, headers=headers_b)
        assert res_3.status_code == 403

        # 4. User without Workspace membership -> DENIED
        res_4 = await client.get(url_ws_a, headers=headers_c)
        assert res_4.status_code == 403
        
        # 6. Raw X-Tenant-ID header without valid WorkspaceContext -> DENIED
        res_6 = await client.get(url_ws_a, headers={"X-Tenant-ID": str(data['workspace_a'].id)})
        assert res_6.status_code == 401
