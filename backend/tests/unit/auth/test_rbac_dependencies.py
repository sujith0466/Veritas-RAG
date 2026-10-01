import uuid
import pytest
from fastapi import FastAPI, Depends, status
from httpx import AsyncClient, ASGITransport

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user, require_role
from backend.core.permissions.rbac import Role
from backend.core.exceptions.auth import InsufficientRoleException, AuthenticationException


def create_rbac_test_app():
    app = FastAPI()

    @app.exception_handler(InsufficientRoleException)
    async def insufficient_role_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationException)
    async def auth_exception_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(exc)})

    @app.get("/member-route")
    async def member_route(user: UserContext = Depends(require_role(Role.MEMBER))):
        return {"status": "ok", "user": user.role}

    @app.get("/viewer-route")
    async def viewer_route(user: UserContext = Depends(require_role(Role.VIEWER))):
        return {"status": "ok", "user": user.role}

    @app.get("/admin-route")
    async def admin_route(user: UserContext = Depends(require_role(Role.ADMIN))):
        return {"status": "ok", "user": user.role}

    @app.get("/owner-route")
    async def owner_route(user: UserContext = Depends(require_role(Role.OWNER))):
        return {"status": "ok", "user": user.role}

    @app.get("/platform-admin-route")
    async def platform_admin_route(user: UserContext = Depends(require_role(Role.PLATFORM_ADMIN))):
        return {"status": "ok", "user": user.role}

    return app


@pytest.mark.asyncio
async def test_require_role_hierarchy_matrix():
    app = create_rbac_test_app()
    transport = ASGITransport(app=app)
    ws_id = uuid.uuid4()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test VIEWER route (accessible to VIEWER, MEMBER, ANALYST, ENGINEER, ADMIN, OWNER, PLATFORM_ADMIN)
        for role in [Role.VIEWER, Role.MEMBER, Role.ANALYST, Role.ENGINEER, Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN]:
            user = UserContext(id=uuid.uuid4(), email=f"{role}@test.com", role=role.value, workspace_id=ws_id)
            app.dependency_overrides[get_current_user] = lambda u=user: u
            res = await client.get("/viewer-route")
            assert res.status_code == 200, f"Role {role} should have access to viewer-route, got {res.status_code}"

        # 2. Test MEMBER route (accessible to MEMBER, ADMIN, OWNER, PLATFORM_ADMIN; denied to VIEWER)
        for role in [Role.MEMBER, Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN]:
            user = UserContext(id=uuid.uuid4(), email=f"{role}@test.com", role=role.value, workspace_id=ws_id)
            app.dependency_overrides[get_current_user] = lambda u=user: u
            res = await client.get("/member-route")
            assert res.status_code == 200, f"Role {role} should have access to member-route, got {res.status_code}"

        for role in [Role.VIEWER]:
            user = UserContext(id=uuid.uuid4(), email=f"{role}@test.com", role=role.value, workspace_id=ws_id)
            app.dependency_overrides[get_current_user] = lambda u=user: u
            res = await client.get("/member-route")
            assert res.status_code == 403, f"Role {role} should be denied on member-route, got {res.status_code}"

        # 3. Test ADMIN route (accessible to ADMIN, OWNER, PLATFORM_ADMIN; denied to VIEWER, MEMBER, ANALYST, ENGINEER)
        for role in [Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN]:
            user = UserContext(id=uuid.uuid4(), email=f"{role}@test.com", role=role.value, workspace_id=ws_id)
            app.dependency_overrides[get_current_user] = lambda u=user: u
            res = await client.get("/admin-route")
            assert res.status_code == 200, f"Role {role} should have access to admin-route, got {res.status_code}"

        for role in [Role.VIEWER, Role.MEMBER, Role.ANALYST, Role.ENGINEER]:
            user = UserContext(id=uuid.uuid4(), email=f"{role}@test.com", role=role.value, workspace_id=ws_id)
            app.dependency_overrides[get_current_user] = lambda u=user: u
            res = await client.get("/admin-route")
            assert res.status_code == 403, f"Role {role} should be denied on admin-route, got {res.status_code}"

        # 4. Test OWNER route (accessible to OWNER, PLATFORM_ADMIN; denied to ADMIN, MEMBER, ANALYST, ENGINEER, VIEWER)
        for role in [Role.OWNER, Role.PLATFORM_ADMIN]:
            user = UserContext(id=uuid.uuid4(), email=f"{role}@test.com", role=role.value, workspace_id=ws_id)
            app.dependency_overrides[get_current_user] = lambda u=user: u
            res = await client.get("/owner-route")
            assert res.status_code == 200, f"Role {role} should have access to owner-route, got {res.status_code}"

        for role in [Role.ADMIN, Role.MEMBER, Role.ANALYST, Role.ENGINEER, Role.VIEWER]:
            user = UserContext(id=uuid.uuid4(), email=f"{role}@test.com", role=role.value, workspace_id=ws_id)
            app.dependency_overrides[get_current_user] = lambda u=user: u
            res = await client.get("/owner-route")
            assert res.status_code == 403, f"Role {role} should be denied on owner-route, got {res.status_code}"

        # 5. Test PLATFORM_ADMIN route (strictly accessible ONLY to PLATFORM_ADMIN)
        user = UserContext(id=uuid.uuid4(), email="padmin@test.com", role=Role.PLATFORM_ADMIN.value, workspace_id=ws_id)
        app.dependency_overrides[get_current_user] = lambda: user
        res = await client.get("/platform-admin-route")
        assert res.status_code == 200

        for role in [Role.OWNER, Role.ADMIN, Role.MEMBER, Role.ANALYST, Role.ENGINEER, Role.VIEWER]:
            user = UserContext(id=uuid.uuid4(), email=f"{role}@test.com", role=role.value, workspace_id=ws_id)
            app.dependency_overrides[get_current_user] = lambda u=user: u
            res = await client.get("/platform-admin-route")
            assert res.status_code == 403, f"Role {role} should be denied on platform-admin-route, got {res.status_code}"

        # 6. Test unauthenticated request without user context
        app.dependency_overrides.pop(get_current_user, None)
        res = await client.get("/admin-route")
        assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


def test_evaluate_role_access_exhaustive_matrix():
    from backend.core.permissions.guards import evaluate_role_access

    # 1. VIEWER remains VIEWER (accesses viewer, denied to higher)
    assert evaluate_role_access(Role.VIEWER, (Role.VIEWER,)) is True
    assert evaluate_role_access(Role.VIEWER, (Role.MEMBER,)) is False
    assert evaluate_role_access(Role.VIEWER, (Role.ANALYST,)) is False
    assert evaluate_role_access(Role.VIEWER, (Role.ENGINEER,)) is False
    assert evaluate_role_access(Role.VIEWER, (Role.ADMIN,)) is False
    assert evaluate_role_access(Role.VIEWER, (Role.OWNER,)) is False
    assert evaluate_role_access(Role.VIEWER, (Role.PLATFORM_ADMIN,)) is False

    # 2. MEMBER remains correct (accesses member and viewer, denied to higher)
    assert evaluate_role_access(Role.MEMBER, (Role.VIEWER,)) is True
    assert evaluate_role_access(Role.MEMBER, (Role.MEMBER,)) is True
    assert evaluate_role_access(Role.MEMBER, (Role.ADMIN,)) is False
    assert evaluate_role_access(Role.MEMBER, (Role.OWNER,)) is False
    assert evaluate_role_access(Role.MEMBER, (Role.PLATFORM_ADMIN,)) is False

    # 3. ANALYST remains correct
    assert evaluate_role_access(Role.ANALYST, (Role.VIEWER,)) is True
    assert evaluate_role_access(Role.ANALYST, (Role.ANALYST,)) is True
    assert evaluate_role_access(Role.ANALYST, (Role.MEMBER,)) is False
    assert evaluate_role_access(Role.ANALYST, (Role.ADMIN,)) is False
    assert evaluate_role_access(Role.ANALYST, (Role.OWNER,)) is False

    # 4. ENGINEER remains correct
    assert evaluate_role_access(Role.ENGINEER, (Role.VIEWER,)) is True
    assert evaluate_role_access(Role.ENGINEER, (Role.ENGINEER,)) is True
    assert evaluate_role_access(Role.ENGINEER, (Role.MEMBER,)) is False
    assert evaluate_role_access(Role.ENGINEER, (Role.ADMIN,)) is False
    assert evaluate_role_access(Role.ENGINEER, (Role.OWNER,)) is False

    # 5. ADMIN inherits lower-level permissions correctly
    assert evaluate_role_access(Role.ADMIN, (Role.VIEWER,)) is True
    assert evaluate_role_access(Role.ADMIN, (Role.MEMBER,)) is True
    assert evaluate_role_access(Role.ADMIN, (Role.ANALYST,)) is True
    assert evaluate_role_access(Role.ADMIN, (Role.ENGINEER,)) is True
    assert evaluate_role_access(Role.ADMIN, (Role.ADMIN,)) is True

    # 6. OWNER inherits lower-level permissions correctly
    assert evaluate_role_access(Role.OWNER, (Role.VIEWER,)) is True
    assert evaluate_role_access(Role.OWNER, (Role.MEMBER,)) is True
    assert evaluate_role_access(Role.OWNER, (Role.ANALYST,)) is True
    assert evaluate_role_access(Role.OWNER, (Role.ENGINEER,)) is True
    assert evaluate_role_access(Role.OWNER, (Role.ADMIN,)) is True
    assert evaluate_role_access(Role.OWNER, (Role.OWNER,)) is True

    # 7. PLATFORM_ADMIN retains platform behavior
    assert evaluate_role_access(Role.PLATFORM_ADMIN, (Role.PLATFORM_ADMIN,)) is True
    assert evaluate_role_access(Role.PLATFORM_ADMIN, (Role.ADMIN,)) is True
    assert evaluate_role_access(Role.PLATFORM_ADMIN, (Role.OWNER,)) is True
    assert evaluate_role_access(Role.PLATFORM_ADMIN, (Role.VIEWER,)) is True

    # 8. OWNER-exclusive permissions remain OWNER-only
    assert evaluate_role_access(Role.OWNER, (Role.OWNER,)) is True

    # 9. ADMIN cannot gain OWNER-only permissions
    assert evaluate_role_access(Role.ADMIN, (Role.OWNER,)) is False
    assert evaluate_role_access(Role.MEMBER, (Role.OWNER,)) is False
    assert evaluate_role_access(Role.VIEWER, (Role.OWNER,)) is False

    # 10. Unauthorized users / suspended users remain denied
    assert evaluate_role_access("invalid_role", (Role.ADMIN,)) is False
    assert evaluate_role_access(Role.ADMIN, (Role.ADMIN,), is_suspended=True) is False
    assert evaluate_role_access(Role.OWNER, (Role.OWNER,), is_suspended=True) is False
    assert evaluate_role_access(Role.PLATFORM_ADMIN, (Role.PLATFORM_ADMIN,), is_suspended=True) is False

