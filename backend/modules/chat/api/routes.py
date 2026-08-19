import uuid

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse

from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.quota import enforce_workspace_quota
from backend.modules.chat.api.dependencies import get_chat_orchestrator, get_chat_repository
from backend.modules.chat.repositories.chat_repository import ChatRepository
from backend.modules.chat.schemas.chat_dto import (
    ChatRequestDTO,
    ChatSessionCreateDTO,
    ChatSessionDTO,
    ChatSessionUpdateDTO,
)
from backend.modules.chat.services.chat_orchestrator import ChatOrchestrator

router = APIRouter(prefix="/chat", tags=["AI Chat"])

def _build_metadata(request: Request) -> ResponseMetadata:
    req_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return ResponseMetadata(request_id=req_id)

@router.get("/sessions", response_model=SuccessResponse[list[ChatSessionDTO]])
async def list_sessions(
    request: Request,
    repo: ChatRepository = Depends(get_chat_repository),
    user: UserContext = Depends(get_current_user)
):
    sessions = await repo.list_sessions(tenant_id=user.tenant_id, user_id=str(user.id))
    return SuccessResponse[list[ChatSessionDTO]](
        data=[ChatSessionDTO.model_validate(s) for s in sessions],
        metadata=_build_metadata(request)
    )

@router.post("/sessions", response_model=SuccessResponse[ChatSessionDTO])
async def create_session(
    dto: ChatSessionCreateDTO,
    request: Request,
    repo: ChatRepository = Depends(get_chat_repository),
    user: UserContext = Depends(get_current_user)
):
    session = await repo.create_session(tenant_id=user.tenant_id, user_id=str(user.id), dto=dto)
    return SuccessResponse[ChatSessionDTO](
        data=ChatSessionDTO.model_validate(session),
        metadata=_build_metadata(request)
    )

@router.get("/sessions/{session_id}", response_model=SuccessResponse[ChatSessionDTO])
async def get_session(
    session_id: str,
    request: Request,
    repo: ChatRepository = Depends(get_chat_repository),
    user: UserContext = Depends(get_current_user)
):
    session = await repo.get_session(session_id=session_id, tenant_id=user.tenant_id, user_id=str(user.id))
    return SuccessResponse[ChatSessionDTO](
        data=ChatSessionDTO.model_validate(session),
        metadata=_build_metadata(request)
    )

from backend.modules.chat.schemas.chat_dto import ChatMessageDTO


@router.get("/sessions/{session_id}/messages", response_model=SuccessResponse[list[ChatMessageDTO]])
async def list_messages(
    session_id: str,
    request: Request,
    limit: int = 50,
    offset: int = 0,
    repo: ChatRepository = Depends(get_chat_repository),
    user: UserContext = Depends(get_current_user)
):
    messages = await repo.list_messages(
        session_id=session_id,
        tenant_id=user.tenant_id,
        user_id=str(user.id),
        limit=limit,
        offset=offset
    )
    return SuccessResponse[list[ChatMessageDTO]](
        data=[ChatMessageDTO.model_validate(m) for m in messages],
        metadata=_build_metadata(request)
    )

@router.put("/sessions/{session_id}", response_model=SuccessResponse[ChatSessionDTO])
async def update_session(
    session_id: str,
    dto: ChatSessionUpdateDTO,
    request: Request,
    repo: ChatRepository = Depends(get_chat_repository),
    user: UserContext = Depends(get_current_user)
):
    session = await repo.update_session(session_id=session_id, tenant_id=user.tenant_id, user_id=str(user.id), dto=dto)
    return SuccessResponse[ChatSessionDTO](
        data=ChatSessionDTO.model_validate(session),
        metadata=_build_metadata(request)
    )

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str,
    repo: ChatRepository = Depends(get_chat_repository),
    user: UserContext = Depends(get_current_user)
):
    await repo.delete_session(session_id=session_id, tenant_id=user.tenant_id, user_id=str(user.id))

@router.post("/sessions/{session_id}/stream")
async def stream_chat(
    session_id: str,
    dto: ChatRequestDTO,
    request: Request,
    orchestrator: ChatOrchestrator = Depends(get_chat_orchestrator),
    user: UserContext = Depends(get_current_user),
    _quota: None = Depends(enforce_workspace_quota()),
):
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    last_event_id = request.headers.get("last-event-id")

    if not user.tenant_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Invalid tenant identifier.")

    return StreamingResponse(
        orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=user.tenant_id,
            user_id=str(user.id),
            query=dto.query,
            correlation_id=correlation_id,
            workspace_id=dto.workspace_id,
            last_event_id=last_event_id
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )
