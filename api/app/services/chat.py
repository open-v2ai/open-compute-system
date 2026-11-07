from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ChatConversation, ChatMessage, User
from app.services.gateway import new_request_id, run_chat_completion


async def list_conversations(db: AsyncSession, user: User) -> list[ChatConversation]:
    query = (
        select(ChatConversation)
        .where(ChatConversation.user_id == user.id, ChatConversation.status == "active")
        .order_by(ChatConversation.updated_at.desc())
    )
    return list((await db.scalars(query)).all())


async def create_conversation(
    db: AsyncSession, *, user: User, model_slug: str, title: str
) -> ChatConversation:
    from app.services.gateway import get_published_model

    await get_published_model(db, model_slug)
    conversation = ChatConversation(user_id=user.id, model_slug=model_slug, title=title[:160])
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def get_conversation(
    db: AsyncSession, *, user: User, conversation_id: str
) -> ChatConversation:
    conversation = await db.scalar(
        select(ChatConversation)
        .where(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user.id,
            ChatConversation.status == "active",
        )
        .options(selectinload(ChatConversation.messages))
    )
    if not conversation:
        raise HTTPException(status_code=404, detail={"code": "CONVERSATION_NOT_FOUND"})
    return conversation


async def delete_conversation(db: AsyncSession, *, user: User, conversation_id: str) -> None:
    conversation = await db.scalar(
        select(ChatConversation)
        .where(ChatConversation.id == conversation_id, ChatConversation.user_id == user.id)
        .with_for_update()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail={"code": "CONVERSATION_NOT_FOUND"})
    conversation.status = "deleted"
    await db.commit()


async def append_user_message_and_complete(
    db: AsyncSession,
    *,
    user: User,
    conversation_id: str,
    content: str,
    max_tokens: int = 512,
    request_id: str | None = None,
) -> tuple[ChatMessage, ChatMessage]:
    conversation = await db.scalar(
        select(ChatConversation)
        .where(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user.id,
            ChatConversation.status == "active",
        )
        .options(selectinload(ChatConversation.messages))
        .with_for_update()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail={"code": "CONVERSATION_NOT_FOUND"})

    user_message = ChatMessage(conversation_id=conversation.id, role="user", content=content)
    db.add(user_message)
    await db.flush()

    prior = await db.scalars(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.asc())
    )
    history = [{"role": message.role, "content": message.content} for message in prior]

    result = await run_chat_completion(
        db,
        user=user,
        model_slug=conversation.model_slug,
        messages=history,
        max_tokens=max_tokens,
        request_id=new_request_id(request_id),
        conversation_id=conversation.id,
    )

    # run_chat_completion commits; reload conversation and attach assistant message.
    conversation = await db.get(ChatConversation, conversation_id)
    assert conversation is not None
    assistant = ChatMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=result.content,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        usage_event_id=result.usage_event_id,
    )
    db.add(assistant)
    if conversation.title == "新对话":
        conversation.title = content.strip()[:40] or "新对话"
    conversation.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(user_message)
    await db.refresh(assistant)
    return user_message, assistant
