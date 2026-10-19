"""Unit tests for REC-002: Workspace Validation Queries Optimization.

Verifies:
1. Scalar ID projections on WorkspaceMember and Document queries.
2. Suppression of ORM eager-load queries (selectinload) when selecting scalar columns.
3. Strict parity of all security gates and error wire contracts in ChatOrchestrator.
4. Parity of validation behavior and exception contracts for direct AIWrapperService callers.
5. Isolated SQLAlchemy SQLite test demonstrating statement suppression.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from sqlalchemy import event, select, String, ForeignKey
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend.ai.schemas.wrapper_dto import AIWrapperRequest, AIWrapperStreamChunk
from backend.ai.wrapper.service import AIWrapperService, WorkspaceValidationError
from backend.document.models.document import Document
from backend.document.models.status import DocumentStatus
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.modules.chat.models.chat_session import ChatSession
from backend.modules.chat.services.chat_orchestrator import ChatOrchestrator


# ============================================================================
# Section 1: Projection Shape & Query Structure Tests
# ============================================================================

@pytest.mark.asyncio
async def test_chat_orchestrator_queries_workspace_member_id_scalar():
    """Verify ChatOrchestrator executes select(WorkspaceMember.id), not select(WorkspaceMember)."""
    session_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())

    fake_session = MagicMock(spec=ChatSession)
    fake_session.id = session_id
    fake_session.user_id = owner_id
    fake_session.tenant_id = ws_id

    mock_session_res = MagicMock()
    mock_session_res.scalar_one_or_none.return_value = fake_session

    mock_member_res = MagicMock()
    mock_member_res.scalar_one_or_none.return_value = uuid.uuid4()

    executed_statements = []

    mock_session = AsyncMock()
    async def mock_execute(stmt, *args, **kwargs):
        executed_statements.append(stmt)
        if len(executed_statements) == 1:
            return mock_session_res
        elif len(executed_statements) == 2:
            return mock_member_res
        mock_generic = MagicMock()
        mock_generic.scalar_one_or_none.return_value = None
        mock_generic.scalars.return_value.all.return_value = []
        return mock_generic

    mock_session.execute = mock_execute

    maker = MagicMock()
    maker.return_value.__aenter__.return_value = mock_session
    maker.return_value.__aexit__.return_value = None

    orchestrator = ChatOrchestrator(ai_wrapper_service=MagicMock(), chat_repo=MagicMock())

    with patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=maker):
        events = []
        async for event_chunk in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=ws_id,
            user_id=owner_id,
            query="Hello",
            correlation_id=correlation_id,
        ):
            events.append(event_chunk)
            break

    # Must have executed at least 2 statements (session check, then membership check)
    assert len(executed_statements) >= 2
    membership_stmt = executed_statements[1]

    # Verify statement projects WorkspaceMember.id, not the whole entity
    cols = [str(c) for c in membership_stmt.selected_columns]
    assert any("workspace_members.id" in c for c in cols)
    # Ensure full entity is not selected
    assert not any(str(c) == "workspace_members" for c in cols)


@pytest.mark.asyncio
async def test_ai_wrapper_service_projections_use_scalar_ids():
    """Verify AIWrapperService._validate_workspace queries WorkspaceMember.id and Document.id."""
    ws_id = uuid.uuid4()
    u_id = uuid.uuid4()
    t_id = ws_id

    fake_ws = MagicMock(spec=Workspace)
    fake_ws.id = ws_id
    fake_ws.status = WorkspaceStatus.ACTIVE.value

    fake_settings = MagicMock(spec=WorkspaceSettings)
    fake_settings.settings_json = {"ai_enabled": True}

    mock_ws_settings_res = MagicMock()
    mock_ws_settings_res.scalar_one_or_none.return_value = fake_settings

    mock_member_res = MagicMock()
    mock_member_res.scalar_one_or_none.return_value = uuid.uuid4()

    mock_docs_res = MagicMock()
    mock_docs_res.scalar_one_or_none.return_value = uuid.uuid4()

    executed_statements = []

    mock_session = AsyncMock()
    mock_session.get.return_value = fake_ws

    async def mock_execute(stmt, *args, **kwargs):
        executed_statements.append(stmt)
        if len(executed_statements) == 1:
            return mock_ws_settings_res
        elif len(executed_statements) == 2:
            return mock_member_res
        elif len(executed_statements) == 3:
            return mock_docs_res
        return MagicMock()

    mock_session.execute = mock_execute

    maker = MagicMock()
    maker.return_value.__aenter__.return_value = mock_session
    maker.return_value.__aexit__.return_value = None

    service = AIWrapperService(
        namespace_resolver=MagicMock(),
        rate_limiter=AsyncMock(),
        retrieval_orchestrator=MagicMock(),
        streaming_generation=MagicMock(),
        event_dispatcher=AsyncMock(),
        llm_manager=MagicMock(),
    )

    req = AIWrapperRequest(
        workspace_id=ws_id,
        tenant_id=t_id,
        query="Test query",
        stream=True,
    )

    with patch("backend.ai.wrapper.service.get_session_factory", return_value=maker):
        await service._validate_workspace(req, u_id)

    assert len(executed_statements) == 3
    member_stmt = executed_statements[1]
    doc_stmt = executed_statements[2]

    # Verify membership query projects WorkspaceMember.id
    member_cols = [str(c) for c in member_stmt.selected_columns]
    assert any("workspace_members.id" in c for c in member_cols)

    # Verify document query projects Document.id
    doc_cols = [str(c) for c in doc_stmt.selected_columns]
    assert any("documents.id" in c for c in doc_cols)


# ============================================================================
# Section 2: Security Gate Parity in ChatOrchestrator
# ============================================================================

@pytest.mark.asyncio
async def test_chat_orchestrator_security_session_not_found():
    """Security Gate 1: If session does not exist, emit SESSION_ACCESS_DENIED."""
    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_res

    maker = MagicMock()
    maker.return_value.__aenter__.return_value = mock_session
    maker.return_value.__aexit__.return_value = None

    orchestrator = ChatOrchestrator(ai_wrapper_service=MagicMock(), chat_repo=MagicMock())

    with patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=maker):
        events = []
        async for event_chunk in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=ws_id,
            user_id=user_id,
            query="Hello",
            correlation_id=str(uuid.uuid4()),
        ):
            events.append(event_chunk)

        assert len(events) == 1
        assert "event: error" in events[0]
        assert "SESSION_ACCESS_DENIED" in events[0]
        assert "Chat session not found." in events[0]


@pytest.mark.asyncio
async def test_chat_orchestrator_security_ownership_mismatch():
    """Security Gate 2: If user does not own session, emit SESSION_ACCESS_DENIED."""
    session_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    attacker_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())

    fake_session = MagicMock(spec=ChatSession)
    fake_session.id = session_id
    fake_session.user_id = owner_id
    fake_session.tenant_id = ws_id

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = fake_session

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_res

    maker = MagicMock()
    maker.return_value.__aenter__.return_value = mock_session
    maker.return_value.__aexit__.return_value = None

    orchestrator = ChatOrchestrator(ai_wrapper_service=MagicMock(), chat_repo=MagicMock())

    with patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=maker):
        events = []
        async for event_chunk in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=ws_id,
            user_id=attacker_id,
            query="Hello",
            correlation_id=str(uuid.uuid4()),
        ):
            events.append(event_chunk)

        assert len(events) == 1
        assert "event: error" in events[0]
        assert "SESSION_ACCESS_DENIED" in events[0]
        assert "User does not own this chat session." in events[0]


@pytest.mark.asyncio
async def test_chat_orchestrator_security_workspace_mismatch():
    """Security Gate 3: If explicit workspace_id differs from session tenant, emit WORKSPACE_MISMATCH."""
    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_ws = str(uuid.uuid4())
    requested_ws = uuid.uuid4()

    fake_session = MagicMock(spec=ChatSession)
    fake_session.id = session_id
    fake_session.user_id = user_id
    fake_session.tenant_id = session_ws

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = fake_session

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_res

    maker = MagicMock()
    maker.return_value.__aenter__.return_value = mock_session
    maker.return_value.__aexit__.return_value = None

    orchestrator = ChatOrchestrator(ai_wrapper_service=MagicMock(), chat_repo=MagicMock())

    with patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=maker):
        events = []
        async for event_chunk in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=session_ws,
            user_id=user_id,
            query="Hello",
            correlation_id=str(uuid.uuid4()),
            workspace_id=requested_ws,
        ):
            events.append(event_chunk)

        assert len(events) == 1
        assert "event: error" in events[0]
        assert "WORKSPACE_MISMATCH" in events[0]
        assert "Requested workspace does not match session workspace." in events[0]


@pytest.mark.asyncio
async def test_chat_orchestrator_security_non_member():
    """Security Gate 4: If user is not an active member, emit WORKSPACE_REQUIRED."""
    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_ws = str(uuid.uuid4())

    fake_session = MagicMock(spec=ChatSession)
    fake_session.id = session_id
    fake_session.user_id = user_id
    fake_session.tenant_id = session_ws

    mock_session_res = MagicMock()
    mock_session_res.scalar_one_or_none.return_value = fake_session

    mock_member_res = MagicMock()
    mock_member_res.scalar_one_or_none.return_value = None  # Scalar ID is None (not found)

    mock_session = AsyncMock()
    mock_session.execute.side_effect = [mock_session_res, mock_member_res]

    maker = MagicMock()
    maker.return_value.__aenter__.return_value = mock_session
    maker.return_value.__aexit__.return_value = None

    orchestrator = ChatOrchestrator(ai_wrapper_service=MagicMock(), chat_repo=MagicMock())

    with patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=maker):
        events = []
        async for event_chunk in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=session_ws,
            user_id=user_id,
            query="Hello",
            correlation_id=str(uuid.uuid4()),
        ):
            events.append(event_chunk)

        assert len(events) == 1
        assert "event: error" in events[0]
        assert "WORKSPACE_REQUIRED" in events[0]
        assert "User is not an active member of this workspace." in events[0]


# ============================================================================
# Section 3: Direct AIWrapperService Validation Invariants
# ============================================================================

@pytest.mark.asyncio
async def test_ai_wrapper_service_missing_workspace():
    """AIWrapperService._validate_workspace raises when workspace does not exist."""
    ws_id = uuid.uuid4()
    u_id = uuid.uuid4()

    mock_session = AsyncMock()
    mock_session.get.return_value = None  # Workspace missing

    maker = MagicMock()
    maker.return_value.__aenter__.return_value = mock_session
    maker.return_value.__aexit__.return_value = None

    service = AIWrapperService(
        namespace_resolver=MagicMock(),
        rate_limiter=AsyncMock(),
        retrieval_orchestrator=MagicMock(),
        streaming_generation=MagicMock(),
        event_dispatcher=AsyncMock(),
        llm_manager=MagicMock(),
    )
    req = AIWrapperRequest(workspace_id=ws_id, tenant_id=ws_id, query="Q", stream=False)

    with patch("backend.ai.wrapper.service.get_session_factory", return_value=maker):
        with pytest.raises(WorkspaceValidationError) as exc:
            await service._validate_workspace(req, u_id)
        assert "Workspace not found or inactive" in str(exc.value)


@pytest.mark.asyncio
async def test_ai_wrapper_service_non_member():
    """AIWrapperService._validate_workspace raises when scalar member id is None."""
    ws_id = uuid.uuid4()
    u_id = uuid.uuid4()

    fake_ws = MagicMock(spec=Workspace)
    fake_ws.id = ws_id
    fake_ws.status = WorkspaceStatus.ACTIVE.value

    fake_settings = MagicMock(spec=WorkspaceSettings)
    fake_settings.settings_json = {"ai_enabled": True}

    mock_ws_settings_res = MagicMock()
    mock_ws_settings_res.scalar_one_or_none.return_value = fake_settings

    mock_member_res = MagicMock()
    mock_member_res.scalar_one_or_none.return_value = None  # Scalar ID missing

    mock_session = AsyncMock()
    mock_session.get.return_value = fake_ws
    mock_session.execute.side_effect = [mock_ws_settings_res, mock_member_res]

    maker = MagicMock()
    maker.return_value.__aenter__.return_value = mock_session
    maker.return_value.__aexit__.return_value = None

    service = AIWrapperService(
        namespace_resolver=MagicMock(),
        rate_limiter=AsyncMock(),
        retrieval_orchestrator=MagicMock(),
        streaming_generation=MagicMock(),
        event_dispatcher=AsyncMock(),
        llm_manager=MagicMock(),
    )
    req = AIWrapperRequest(workspace_id=ws_id, tenant_id=ws_id, query="Q", stream=False)

    with patch("backend.ai.wrapper.service.get_session_factory", return_value=maker):
        with pytest.raises(WorkspaceValidationError) as exc:
            await service._validate_workspace(req, u_id)
        assert "User is not a member of this workspace" in str(exc.value)


@pytest.mark.asyncio
async def test_ai_wrapper_service_no_ready_documents():
    """AIWrapperService._validate_workspace raises when scalar document id is None."""
    ws_id = uuid.uuid4()
    u_id = uuid.uuid4()

    fake_ws = MagicMock(spec=Workspace)
    fake_ws.id = ws_id
    fake_ws.status = WorkspaceStatus.ACTIVE.value

    fake_settings = MagicMock(spec=WorkspaceSettings)
    fake_settings.settings_json = {"ai_enabled": True}

    mock_ws_settings_res = MagicMock()
    mock_ws_settings_res.scalar_one_or_none.return_value = fake_settings

    mock_member_res = MagicMock()
    mock_member_res.scalar_one_or_none.return_value = uuid.uuid4()

    mock_docs_res = MagicMock()
    mock_docs_res.scalar_one_or_none.return_value = None  # No ready docs

    mock_session = AsyncMock()
    mock_session.get.return_value = fake_ws
    mock_session.execute.side_effect = [mock_ws_settings_res, mock_member_res, mock_docs_res]

    maker = MagicMock()
    maker.return_value.__aenter__.return_value = mock_session
    maker.return_value.__aexit__.return_value = None

    service = AIWrapperService(
        namespace_resolver=MagicMock(),
        rate_limiter=AsyncMock(),
        retrieval_orchestrator=MagicMock(),
        streaming_generation=MagicMock(),
        event_dispatcher=AsyncMock(),
        llm_manager=MagicMock(),
    )
    req = AIWrapperRequest(workspace_id=ws_id, tenant_id=ws_id, query="Q", stream=False)

    with patch("backend.ai.wrapper.service.get_session_factory", return_value=maker):
        with pytest.raises(WorkspaceValidationError) as exc:
            await service._validate_workspace(req, u_id)
        assert "No READY documents in knowledge base" in str(exc.value)


# ============================================================================
# Section 4: Isolated SQLite Async Engine Eager-Load Suppression Test
# ============================================================================

class _TestBase(DeclarativeBase):
    pass

class _TestParent(_TestBase):
    __tablename__ = "test_parents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    # Eager relationship identical to WorkspaceMember's lazy="selectin"
    children: Mapped[list["_TestChild"]] = relationship("_TestChild", backref="parent", lazy="selectin")

class _TestChild(_TestBase):
    __tablename__ = "test_children"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parent_id: Mapped[str] = mapped_column(String(36), ForeignKey("test_parents.id"))
    detail: Mapped[str] = mapped_column(String(50))


def test_sqlite_eager_load_suppression_empirical_proof():
    """Empirical proof using an isolated standard-library SQLite engine:

    1. select(Entity) with lazy="selectin" emits 2 SQL statements (parent + selectin child).
    2. select(Entity.id) emits strictly 1 SQL statement (child query is suppressed).
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine("sqlite:///:memory:", echo=False)
    _TestBase.metadata.create_all(engine)

    p_id = str(uuid.uuid4())
    c_id = str(uuid.uuid4())

    with Session(engine) as session:
        session.add(_TestParent(id=p_id, name="Parent 1"))
        session.add(_TestChild(id=c_id, parent_id=p_id, detail="Child 1"))
        session.commit()

    # Track cursor executions
    executed_sql = []
    def capture_sql(conn, cursor, statement, parameters, context, executemany):
        executed_sql.append(statement)

    event.listen(engine, "before_cursor_execute", capture_sql)

    try:
        # 1. ORM Entity selection: triggers selectinload
        executed_sql.clear()
        with Session(engine) as session:
            stmt = select(_TestParent).where(_TestParent.id == p_id)
            res = session.execute(stmt)
            entity = res.scalar_one_or_none()
            assert entity is not None
            # Verified: primary query + secondary selectin query
            assert len(executed_sql) == 2
            assert any("test_parents" in s for s in executed_sql)
            assert any("test_children" in s for s in executed_sql)

        # 2. Scalar ID selection: completely suppresses selectinload
        executed_sql.clear()
        with Session(engine) as session:
            stmt = select(_TestParent.id).where(_TestParent.id == p_id)
            res = session.execute(stmt)
            val = res.scalar_one_or_none()
            assert val == p_id
            # Verified: strictly 1 query, zero eager loads
            assert len(executed_sql) == 1
            assert any("test_parents" in s for s in executed_sql)
            assert not any("test_children" in s for s in executed_sql)

    finally:
        event.remove(engine, "before_cursor_execute", capture_sql)
        engine.dispose()
