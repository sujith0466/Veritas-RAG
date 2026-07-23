from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from backend.modules.chat.models import ChatSession, ChatMessage
from backend.modules.chat.schemas import ChatSessionCreateDTO, ChatSessionUpdateDTO, ChatMessageCreateDTO

class ChatRepository:
    """Repository for managing ChatSessions and ChatMessages."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_sessions(self, tenant_id: str, user_id: str, limit: int = 50, offset: int = 0) -> List[ChatSession]:
        stmt = (
            select(ChatSession)
            .where(ChatSession.tenant_id == tenant_id, ChatSession.user_id == user_id)
            .options(selectinload(ChatSession.messages))
            .order_by(desc(ChatSession.updated_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_session(self, session_id: str, tenant_id: str, user_id: str, include_messages: bool = True) -> ChatSession:
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.tenant_id == tenant_id,
            ChatSession.user_id == user_id
        )
        if include_messages:
            stmt = stmt.options(selectinload(ChatSession.messages))
            
        result = await self.session.execute(stmt)
        session_obj = result.scalars().first()
        
        if not session_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat session not found or access denied."
            )
        return session_obj

    async def create_session(self, tenant_id: str, user_id: str, dto: ChatSessionCreateDTO) -> ChatSession:
        new_session = ChatSession(
            tenant_id=tenant_id,
            user_id=user_id,
            title=dto.title
        )
        self.session.add(new_session)
        await self.session.commit()
        # Fetch the newly created session with eager loaded relationships
        return await self.get_session(new_session.id, tenant_id, user_id, include_messages=True)

    async def update_session(self, session_id: str, tenant_id: str, user_id: str, dto: ChatSessionUpdateDTO) -> ChatSession:
        session_obj = await self.get_session(session_id, tenant_id, user_id, include_messages=True)
        
        if dto.title is not None:
            session_obj.title = dto.title
        if dto.pinned is not None:
            session_obj.pinned = dto.pinned
        if dto.archived is not None:
            session_obj.archived = dto.archived
            
        await self.session.commit()
        return session_obj

    async def delete_session(self, session_id: str, tenant_id: str, user_id: str) -> None:
        session_obj = await self.get_session(session_id, tenant_id, user_id, include_messages=False)
        await self.session.delete(session_obj)
        await self.session.commit()

    async def add_message(self, session_id: str, tenant_id: str, user_id: str, dto: ChatMessageCreateDTO) -> ChatMessage:
        # Verify ownership
        session_obj = await self.get_session(session_id, tenant_id, user_id, include_messages=False)
        
        message = ChatMessage(
            session_id=session_obj.id,
            role=dto.role,
            message=dto.message,
            citations=dto.citations,
            reliability_score=dto.reliability_score,
            metadata_json=dto.metadata_json
        )
        self.session.add(message)
        
        # Touch the session updated_at
        from datetime import datetime, timezone
        session_obj.updated_at = datetime.now(timezone.utc)
        
        await self.session.commit()
        return message
