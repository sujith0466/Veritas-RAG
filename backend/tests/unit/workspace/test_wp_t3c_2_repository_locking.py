"""Unit tests for Package T-3.C Work Package WP-T3C-2.

Verifies:
1. WorkspaceRepository.get_by_id_for_update builds a SELECT ... FOR UPDATE query.
2. WorkspaceMemberRepository.count_non_deleted_owners counts owners matching
   the canonical database predicate (role = 'OWNER' AND is_deleted = false).
"""

import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_member import WorkspaceMember, WorkspaceRole
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository


class TestWorkspaceRepositoryLocking:
    """Tests pessimistic row-locking methods in WorkspaceRepository."""

    @pytest.mark.asyncio
    async def test_get_by_id_for_update_executes_with_for_update(self):
        """Verify get_by_id_for_update compiles with_for_update and filters by id and is_deleted."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = Workspace(
            name="Test Workspace",
            slug="test-workspace",
            public_id="ws_12345",
        )
        session.execute.return_value = mock_result

        repo = WorkspaceRepository(session)
        ws_id = uuid.uuid4()
        workspace = await repo.get_by_id_for_update(ws_id)

        assert workspace is not None
        assert session.execute.called
        call_args = session.execute.call_args[0]
        stmt = call_args[0]

        # Verify compiled SQL contains FOR UPDATE
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "FOR UPDATE" in compiled
        assert "workspaces.is_deleted = false" in compiled or "workspaces.is_deleted = 0" in compiled
        assert ws_id.hex in compiled or str(ws_id) in compiled


class TestWorkspaceMemberRepositoryPredicateQueries:
    """Tests invariant count queries in WorkspaceMemberRepository."""

    @pytest.mark.asyncio
    async def test_count_non_deleted_owners_matches_database_predicate(self):
        """Verify count_non_deleted_owners queries role='OWNER' and is_deleted=false without status filter."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        session.execute.return_value = mock_result

        repo = WorkspaceMemberRepository(session)
        ws_id = uuid.uuid4()
        count = await repo.count_non_deleted_owners(ws_id)

        assert count == 1
        assert session.execute.called
        stmt = session.execute.call_args[0][0]

        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "count" in compiled.lower()
        assert "workspace_members.role = 'OWNER'" in compiled
        assert "workspace_members.is_deleted = false" in compiled or "workspace_members.is_deleted = 0" in compiled
        # Crucial: Must NOT filter by status=ACTIVE (suspended owners must be included in invariant count)
        assert "status" not in compiled.lower()
