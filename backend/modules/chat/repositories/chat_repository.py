from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.modules.chat.models import ChatMessage, ChatSession
from backend.modules.chat.schemas import (
    ChatMessageCreateDTO,
    ChatSessionCreateDTO,
    ChatSessionUpdateDTO,
)


class ChatRepository:
    """Repository for managing ChatSessions and ChatMessages."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_sessions(self, tenant_id: str, user_id: str, limit: int = 50, offset: int = 0) -> list[ChatSession]:
        stmt = (
            select(ChatSession)
            .where(ChatSession.tenant_id == tenant_id, ChatSession.user_id == user_id, ChatSession.archived == False)
            .order_by(desc(ChatSession.updated_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_messages(self, session_id: str, tenant_id: str, user_id: str, limit: int = 50, offset: int = 0) -> list[ChatMessage]:
        # Verify ownership first
        await self.get_session(session_id, tenant_id, user_id, include_messages=False)

        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
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
        session_obj.updated_at = datetime.now(UTC)

        await self.session.commit()
        return message

    async def get_message(self, session_id: str, message_id: str) -> ChatMessage | None:
        """Fetch a specific message within a session."""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.id == message_id, ChatMessage.session_id == session_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def rewind_session_from(
        self, session_id: str, target_message_id: str, tenant_id: str, user_id: str
    ) -> int:
        """Deterministically rewind a session by deleting target message and all subsequent turns.
        
        Guarantees:
        - Target message is verified to belong to the authorized session.
        - Deletion boundary uses canonical ordering: (created_at ASC, id ASC).
        - Exactly target and subsequent messages are deleted; earlier messages are untouched.
        - Same-timestamp messages cannot cause accidental deletion.
        - Cross-session/tenant deletion is impossible.
        - Operation is atomic.
        """
        # Step 1: Verify session ownership
        await self.get_session(session_id, tenant_id, user_id, include_messages=False)

        # Step 2: Fetch all message IDs in the session in deterministic canonical order
        stmt = (
            select(ChatMessage.id)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        result = await self.session.execute(stmt)
        ordered_ids = list(result.scalars().all())

        # Step 3: Find exact index of target message
        if target_message_id not in ordered_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target message not found in this chat session."
            )

        target_idx = ordered_ids.index(target_message_id)

        # Step 4: Isolate exact list of IDs to delete (target + all subsequent turns)
        ids_to_delete = ordered_ids[target_idx:]

        # Step 5: Execute atomic bulk deletion
        delete_stmt = delete(ChatMessage).where(ChatMessage.id.in_(ids_to_delete))
        await self.session.execute(delete_stmt)

        # Step 6: Touch session updated_at and commit transaction
        session_obj = await self.session.get(ChatSession, session_id)
        if session_obj:
            session_obj.updated_at = datetime.now(UTC)

        await self.session.commit()
        return len(ids_to_delete)

    async def update_message_feedback(
        self,
        session_id: str,
        message_id: str,
        tenant_id: str,
        user_id: str,
        rating: str | None
    ) -> ChatMessage:
        """Update or clear feedback rating on an assistant message in metadata_json.
        
        Guarantees:
        - Session ownership is verified.
        - Message must exist and have role == 'assistant'.
        - Server derives user_id and timestamp; client cannot spoof identity.
        """
        # Step 1: Verify session ownership
        await self.get_session(session_id, tenant_id, user_id, include_messages=False)

        # Step 2: Fetch target message
        message = await self.get_message(session_id=session_id, message_id=message_id)
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found in this chat session."
            )

        if message.role != "assistant":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feedback can only be submitted for assistant messages."
            )

        # Step 3: Update metadata_json with server-authoritative fields
        meta = dict(message.metadata_json or {})
        if rating is None:
            meta.pop("feedback", None)
            meta.pop("feedback_at", None)
            meta.pop("feedback_by", None)
        else:
            meta["feedback"] = rating
            meta["feedback_at"] = datetime.now(UTC).isoformat()
            meta["feedback_by"] = user_id

        message.metadata_json = meta
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def stream_workspace_messages(self, tenant_ids: list[str] | str, start_date=None, end_date=None):
        if isinstance(tenant_ids, str):
            tenant_ids = [tenant_ids]

        stmt = (
            select(ChatMessage, ChatSession.user_id, ChatSession.title)
            .join(ChatSession, ChatMessage.session_id == ChatSession.id)
            .where(ChatSession.tenant_id.in_(tenant_ids))
            .order_by(ChatMessage.created_at.asc())
        )

        if start_date:
            stmt = stmt.where(ChatMessage.created_at >= start_date)
        if end_date:
            stmt = stmt.where(ChatMessage.created_at <= end_date)

        # Using stream to fetch in batches
        result = await self.session.stream(stmt.execution_options(yield_per=1000))
        async for row in result:
            yield row
