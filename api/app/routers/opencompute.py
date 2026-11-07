from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import current_user
from app.models import ApiKey, InferenceModel, UsageEvent, User
from app.schemas import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    ChatCompletionRequest,
    ChatMessageResponse,
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationSendRequest,
    ConversationSendResponse,
    InferenceModelResponse,
    OpenAIModelCard,
    OpenAIModelListResponse,
    UsageEventResponse,
)
from app.services import chat as chat_service
from app.services.gateway import create_api_key as gateway_create_api_key
from app.services.gateway import (
    new_request_id,
    openai_completion_payload,
    resolve_api_key,
    run_chat_completion,
    stream_chat_completion,
)
from app.services.gateway import revoke_api_key as gateway_revoke_api_key

router = APIRouter(tags=["opencompute"])


@router.get("/models", response_model=OpenAIModelListResponse)
async def list_openai_models(db: AsyncSession = Depends(get_db)) -> OpenAIModelListResponse:
    rows = list(
        (
            await db.scalars(
                select(InferenceModel)
                .where(InferenceModel.status == "published")
                .order_by(InferenceModel.slug.asc())
            )
        ).all()
    )
    now = int(time.time())
    return OpenAIModelListResponse(
        data=[
            OpenAIModelCard(id=row.slug, created=now, owned_by="opencompute") for row in rows
        ]
    )


@router.get("/inference/models", response_model=list[InferenceModelResponse])
async def list_inference_catalog(db: AsyncSession = Depends(get_db)) -> list[InferenceModel]:
    return list(
        (
            await db.scalars(
                select(InferenceModel)
                .where(InferenceModel.status == "published")
                .order_by(InferenceModel.slug.asc())
            )
        ).all()
    )


@router.post("/chat/completions")
async def chat_completions(
    payload: ChatCompletionRequest,
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    user, api_key = await resolve_api_key(db, authorization)
    request_id = new_request_id(getattr(request.state, "request_id", None))
    messages = [item.model_dump() for item in payload.messages]
    if payload.stream:
        generator = stream_chat_completion(
            db,
            user=user,
            model_slug=payload.model,
            messages=messages,
            max_tokens=payload.max_tokens,
            request_id=request_id,
            temperature=payload.temperature,
            api_key=api_key,
        )
        return StreamingResponse(generator, media_type="text/event-stream")

    result = await run_chat_completion(
        db,
        user=user,
        model_slug=payload.model,
        messages=messages,
        max_tokens=payload.max_tokens,
        request_id=request_id,
        temperature=payload.temperature,
        api_key=api_key,
    )
    return openai_completion_payload(result)


@router.get("/inference/keys", response_model=list[ApiKeyResponse])
async def list_keys(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> list[ApiKey]:
    return list(
        (
            await db.scalars(
                select(ApiKey)
                .where(ApiKey.user_id == user.id)
                .order_by(ApiKey.created_at.desc())
            )
        ).all()
    )


@router.post("/inference/keys", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_key(
    payload: ApiKeyCreateRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeyCreatedResponse:
    key, secret = await gateway_create_api_key(
        db,
        user=user,
        name=payload.name,
        credit_limit_cents=payload.credit_limit_cents,
        rpm_limit=payload.rpm_limit,
        tpm_limit=payload.tpm_limit,
        allowed_models=payload.allowed_models,
    )
    return ApiKeyCreatedResponse(
        **ApiKeyResponse.model_validate(key).model_dump(),
        secret=secret,
    )


@router.post("/inference/keys/{key_id}/revoke", response_model=ApiKeyResponse)
async def revoke_key(
    key_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    return await gateway_revoke_api_key(db, user=user, key_id=key_id)


@router.get("/inference/usage", response_model=list[UsageEventResponse])
async def list_usage(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> list[UsageEvent]:
    return list(
        (
            await db.scalars(
                select(UsageEvent)
                .where(UsageEvent.user_id == user.id)
                .order_by(UsageEvent.created_at.desc())
                .limit(200)
            )
        ).all()
    )


@router.get("/inference/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> list[ConversationResponse]:
    rows = await chat_service.list_conversations(db, user)
    return [ConversationResponse.model_validate(row) for row in rows]


@router.post("/inference/conversations", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    payload: ConversationCreateRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    row = await chat_service.create_conversation(
        db, user=user, model_slug=payload.model_slug, title=payload.title
    )
    return ConversationResponse.model_validate(row)


@router.get(
    "/inference/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
)
async def get_conversation(
    conversation_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    row = await chat_service.get_conversation(db, user=user, conversation_id=conversation_id)
    messages = sorted(row.messages, key=lambda item: item.created_at)
    return ConversationDetailResponse(
        **ConversationResponse.model_validate(row).model_dump(),
        messages=[ChatMessageResponse.model_validate(message) for message in messages],
    )


@router.delete("/inference/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await chat_service.delete_conversation(db, user=user, conversation_id=conversation_id)


@router.post(
    "/inference/conversations/{conversation_id}/messages",
    response_model=ConversationSendResponse,
)
async def send_conversation_message(
    conversation_id: str,
    payload: ConversationSendRequest,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationSendResponse:
    user_message, assistant = await chat_service.append_user_message_and_complete(
        db,
        user=user,
        conversation_id=conversation_id,
        content=payload.content,
        max_tokens=payload.max_tokens,
        request_id=getattr(request.state, "request_id", None),
    )
    return ConversationSendResponse(
        user_message=ChatMessageResponse.model_validate(user_message),
        assistant_message=ChatMessageResponse.model_validate(assistant),
    )
