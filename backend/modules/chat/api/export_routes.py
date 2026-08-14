import csv
import json
import uuid
from datetime import datetime
from io import StringIO
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db, get_workspace_member_repository
from backend.models.entities.workspace_member import WorkspaceMember, WorkspaceRole
from backend.modules.chat.repositories.chat_repository import ChatRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository

router = APIRouter(prefix="/workspaces/{workspace_id}/chat", tags=["AI Chat Export"])


async def get_chat_repository_with_db(session: AsyncSession = Depends(get_db)) -> ChatRepository:
    return ChatRepository(session=session)


async def _verify_workspace_access(
    workspace_id: uuid.UUID,
    user: UserContext,
    member_repo: WorkspaceMemberRepository,
    allowed_roles: tuple[str, ...] = (WorkspaceRole.OWNER.value, WorkspaceRole.ADMIN.value),
) -> None:
    """Verify the user is a member of the workspace with the required role.
    
    Raises HTTP 403 if not permitted.
    """
    membership: WorkspaceMember | None = await member_repo.get_membership(
        workspace_id=workspace_id,
        user_id=user.id,
        include_suspended=False,
    )
    
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not a member of this workspace.",
        )
    
    if membership.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only workspace owners and admins can export chat history.",
        )


@router.get("/export", response_class=StreamingResponse)
async def export_chat_history(
    workspace_id: uuid.UUID,
    format: str = Query("json", description="Export format: json or csv"),
    start_date: datetime | None = Query(None, description="Start date for filtering"),
    end_date: datetime | None = Query(None, description="End date for filtering"),
    user: UserContext = Depends(get_current_user),
    member_repo: WorkspaceMemberRepository = Depends(get_workspace_member_repository),
    repo: ChatRepository = Depends(get_chat_repository_with_db),
):
    """Export workspace chat history as JSON or CSV.
    
    Access control:
    - Only workspace OWNER or ADMIN can export.
    - MEMBER and VIEWER are denied (403).
    - Users from other workspaces are denied (403).
    
    Memory safety:
    - Uses streaming to avoid loading the full dataset into memory.
    """
    # DB-level cross-workspace isolation and role check
    await _verify_workspace_access(workspace_id, user, member_repo)

    if format not in ["json", "csv"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported export format. Use 'json' or 'csv'.",
        )

    ws_id_str = str(workspace_id)

    async def generate_json() -> AsyncGenerator[str, None]:
        yield "[\n"
        first = True
        async for row in repo.stream_workspace_messages(ws_id_str, start_date, end_date):
            message, user_id, session_title = row
            if not first:
                yield ",\n"
            first = False

            data = {
                "session_id": message.session_id,
                "session_title": session_title,
                "user_id": user_id,
                "message_id": message.id,
                "role": message.role,
                "message": message.message,
                "created_at": message.created_at.isoformat() if message.created_at else None,
                "citations": message.citations,
                "reliability_score": message.reliability_score,
                "metadata": message.metadata_json,
            }
            yield json.dumps(data)
        yield "\n]"

    async def generate_csv() -> AsyncGenerator[str, None]:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "session_id", "session_title", "user_id", "message_id",
            "role", "message", "created_at", "citations",
            "reliability_score", "metadata",
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        async for row in repo.stream_workspace_messages(ws_id_str, start_date, end_date):
            message, user_id, session_title = row
            writer.writerow([
                message.session_id,
                session_title,
                user_id,
                message.id,
                message.role,
                message.message,
                message.created_at.isoformat() if message.created_at else "",
                json.dumps(message.citations) if message.citations else "",
                message.reliability_score if message.reliability_score is not None else "",
                json.dumps(message.metadata_json) if message.metadata_json else "",
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    filename = f"chat_export_{workspace_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{format}"

    if format == "json":
        return StreamingResponse(
            generate_json(),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    else:
        return StreamingResponse(
            generate_csv(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
