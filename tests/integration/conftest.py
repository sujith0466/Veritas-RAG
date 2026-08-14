import pytest
import uuid
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
warnings.filterwarnings("ignore", category=FutureWarning, module=".*google.*")
from backend.models.entities import *
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_member import WorkspaceMember, WorkspaceRole
from backend.database.engine import get_session_factory, get_engine
from backend.models.base import BaseModel

import pytest_asyncio

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)
        await conn.run_sync(BaseModel.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def isolation_test_data(setup_database):
    factory = get_session_factory()
    async with factory() as session:
        user_a = User(email=f"usera_{uuid.uuid4().hex[:6]}@example.com", role="viewer", is_active=True, is_verified=True)
        user_b = User(email=f"userb_{uuid.uuid4().hex[:6]}@example.com", role="viewer", is_active=True, is_verified=True)
        user_c = User(email=f"userc_{uuid.uuid4().hex[:6]}@example.com", role="viewer", is_active=True, is_verified=True)
        
        ws_slug_a = f"wsa-{uuid.uuid4().hex[:6]}"
        ws_slug_b = f"wsb-{uuid.uuid4().hex[:6]}"
        workspace_a = Workspace(name="Workspace A", slug=ws_slug_a, storage_prefix=ws_slug_a, qdrant_namespace=ws_slug_a)
        workspace_b = Workspace(name="Workspace B", slug=ws_slug_b, storage_prefix=ws_slug_b, qdrant_namespace=ws_slug_b)
        
        session.add_all([user_a, user_b, user_c, workspace_a, workspace_b])
        await session.commit()
        await session.refresh(user_a)
        await session.refresh(user_b)
        await session.refresh(user_c)
        await session.refresh(workspace_a)
        await session.refresh(workspace_b)

        member_a = WorkspaceMember(workspace_id=workspace_a.id, user_id=user_a.id, role=WorkspaceRole.OWNER.value)
        member_b = WorkspaceMember(workspace_id=workspace_b.id, user_id=user_b.id, role=WorkspaceRole.OWNER.value)
        
        session.add_all([member_a, member_b])
        user_a.workspace_name = str(workspace_a.id)
        user_b.workspace_name = str(workspace_b.id)
        
        await session.commit()
        yield {
            "user_a": user_a,
            "user_b": user_b,
            "user_c": user_c,
            "workspace_a": workspace_a,
            "workspace_b": workspace_b
        }

from backend.cache.client import close_cache

@pytest_asyncio.fixture(scope="function", autouse=True)
async def cleanup_cache():
    # Ensure cache is closed between tests to avoid "Event loop is closed" errors
    # with the global Redis connection pool.
    yield
    await close_cache()
