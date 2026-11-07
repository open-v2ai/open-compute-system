from __future__ import annotations

import os
import secrets
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models import (
    ApiKey,
    AutoRouterConfig,
    InferenceModel,
    InferenceReplica,
    UsageEvent,
    User,
)
from app.providers.inference_base import InferenceBackend, InferenceBackendError, InferenceTarget
from app.providers.inference_mock import MockInferenceBackend, estimate_prompt_tokens, hash_api_key
from app.providers.inference_openai import OpenAICompatibleInferenceBackend
from app.services.rate_limit import consume_api_key_limit
from app.services.wallet import (
    available_micros,
    debit_cents,
    estimate_max_cost_micros,
    settle_inference_micros,
)

_mock_backend = MockInferenceBackend()
_openai_compatible_backend = OpenAICompatibleInferenceBackend()


@dataclass(slots=True)
class GatewayResult:
    completion_id: str
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    replica_label: str
    usage_event_id: str
    debit_cents: int
    cost_micros: int
    latency_ms: int
    routed_model: str | None = None
    routing_tier: str | None = None
    routing_decision_source: str | None = None
    classifier_model: str | None = None
    classifier_latency_ms: int = 0


@dataclass(slots=True)
class RouteResolution:
    execution_model: InferenceModel
    tier: str | None = None
    decision_source: str | None = None
    classifier_model_slug: str | None = None
    classifier_latency_ms: int = 0


def backend_for_model(model: InferenceModel) -> InferenceBackend:
    if model.backend_type == "mock":
        if settings.app_env == "production" and not settings.allow_mock_inference_in_production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "MOCK_INFERENCE_FORBIDDEN", "message": "生产环境禁止 Mock 推理"},
            )
        return _mock_backend
    if model.backend_type == "openai_compatible":
        return _openai_compatible_backend
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={"code": "BACKEND_UNSUPPORTED", "message": "推理后端类型不受支持"},
    )


def target_for_replica(model: InferenceModel, replica: InferenceReplica) -> InferenceTarget:
    api_key = None
    if replica.credential_env_var:
        api_key = os.environ.get(replica.credential_env_var)
        if not api_key:
            raise InferenceBackendError(
                "UPSTREAM_CREDENTIAL_MISSING", "推理端点凭据未配置"
            )
    return InferenceTarget(
        endpoint=replica.endpoint,
        model=replica.upstream_model or model.slug,
        replica_label=replica.label,
        api_key=api_key,
        timeout_seconds=replica.timeout_seconds,
    )


async def get_published_model(db: AsyncSession, slug: str) -> InferenceModel:
    model = await db.scalar(
        select(InferenceModel)
        .where(InferenceModel.slug == slug, InferenceModel.status == "published")
        .options(
            selectinload(InferenceModel.replicas),
            selectinload(InferenceModel.router_config),
        )
    )
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MODEL_NOT_FOUND", "message": "模型不存在或未上架"},
        )
    return model


async def _get_published_model_by_id(db: AsyncSession, model_id: str) -> InferenceModel | None:
    return await db.scalar(
        select(InferenceModel)
        .where(InferenceModel.id == model_id, InferenceModel.status == "published")
        .options(selectinload(InferenceModel.replicas))
    )


def _classifier_messages(messages: list[dict[str, Any]], max_tokens: int) -> list[dict[str, str]]:
    latest_user = next(
        (
            str(item.get("content", "")).strip()
            for item in reversed(messages)
            if item.get("role") == "user"
        ),
        "",
    )
    latest_user = latest_user[:6000]
    return [
        {
            "role": "system",
            "content": (
                "AUTO_ROUTER_CLASSIFIER_V1\n"
                "Classify the request as simple or complex. Complex means it needs multi-step "
                "reasoning, non-trivial coding, mathematics, careful constraint handling, or long "
                "context synthesis. Output exactly one lowercase word: simple or complex."
            ),
        },
        {
            "role": "user",
            "content": (
                f"conversation_messages={len(messages)}; requested_max_tokens={max_tokens}\n"
                f"request={latest_user}"
            ),
        },
    ]


def _parse_routing_tier(content: str) -> str | None:
    normalized = content.strip().lower().strip("`\"' .,:;{}[]")
    if normalized in {"simple", "complex"}:
        return normalized
    for tier in ("simple", "complex"):
        if f'"tier":"{tier}"' in normalized.replace(" ", ""):
            return tier
    return None


async def _classify_route(
    db: AsyncSession,
    *,
    config: AutoRouterConfig,
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> tuple[str, str, str | None, int]:
    started = time.perf_counter()
    classifier = await _get_published_model_by_id(db, config.classifier_model_id)
    if classifier and classifier.backend_type != "auto_router":
        backend = backend_for_model(classifier)
        for replica in ordered_replicas(classifier):
            try:
                target = target_for_replica(classifier, replica)
                target.timeout_seconds = min(
                    target.timeout_seconds,
                    config.classifier_timeout_seconds,
                )
                result = await backend.chat_completions(
                    messages=_classifier_messages(messages, max_tokens),
                    max_tokens=8,
                    temperature=0,
                    target=target,
                    fail_once=replica.fail_once,
                )
                if replica.fail_once:
                    replica.fail_once = False
                tier = _parse_routing_tier(result.content)
                if tier:
                    return (
                        tier,
                        "classifier",
                        classifier.slug,
                        int((time.perf_counter() - started) * 1000),
                    )
            except InferenceBackendError:
                continue
    return (
        config.fallback_tier,
        "configured_fallback",
        classifier.slug if classifier else None,
        int((time.perf_counter() - started) * 1000),
    )


async def resolve_route(
    db: AsyncSession,
    *,
    requested_model: InferenceModel,
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> RouteResolution:
    if requested_model.backend_type != "auto_router":
        return RouteResolution(execution_model=requested_model)
    config = requested_model.router_config
    if not config:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AUTO_ROUTER_NOT_CONFIGURED"},
        )
    tier, source, classifier_slug, classifier_latency_ms = await _classify_route(
        db,
        config=config,
        messages=messages,
        max_tokens=max_tokens,
    )
    target_id = config.simple_model_id if tier == "simple" else config.complex_model_id
    alternate_id = config.complex_model_id if tier == "simple" else config.simple_model_id
    execution_model = await _get_published_model_by_id(db, target_id)
    if not execution_model or not ordered_replicas(execution_model):
        execution_model = await _get_published_model_by_id(db, alternate_id)
        if not execution_model or not ordered_replicas(execution_model):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "AUTO_ROUTER_TARGETS_UNAVAILABLE"},
            )
        tier = "complex" if tier == "simple" else "simple"
        source = "availability_fallback"
    return RouteResolution(
        execution_model=execution_model,
        tier=tier,
        decision_source=source,
        classifier_model_slug=classifier_slug,
        classifier_latency_ms=classifier_latency_ms,
    )


def ordered_replicas(model: InferenceModel) -> list[InferenceReplica]:
    healthy = [
        replica
        for replica in model.replicas
        if replica.enabled and replica.health_status == "healthy"
    ]
    healthy.sort(key=lambda item: (-item.weight, item.label))
    return healthy


async def resolve_api_key(db: AsyncSession, authorization: str | None) -> tuple[User, ApiKey]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "API_KEY_REQUIRED", "message": "缺少 API Key"},
        )
    raw = authorization.split(" ", 1)[1].strip()
    if not raw.startswith("ocs_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "API_KEY_INVALID", "message": "API Key 无效"},
        )
    key = await db.scalar(
        select(ApiKey).where(ApiKey.key_hash == hash_api_key(raw), ApiKey.status == "active")
    )
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "API_KEY_INVALID", "message": "API Key 无效或已吊销"},
        )
    user = await db.get(User, key.user_id)
    if not user or user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ACCOUNT_UNAVAILABLE", "message": "账户不可用"},
        )
    return user, key


async def create_api_key(
    db: AsyncSession,
    *,
    user: User,
    name: str,
    credit_limit_cents: int | None,
    rpm_limit: int,
    tpm_limit: int,
    allowed_models: list[str],
) -> tuple[ApiKey, str]:
    raw = f"ocs_{secrets.token_urlsafe(32)}"
    key = ApiKey(
        user_id=user.id,
        name=name,
        key_prefix=raw[:12],
        key_hash=hash_api_key(raw),
        credit_limit_cents=credit_limit_cents,
        rpm_limit=rpm_limit,
        tpm_limit=tpm_limit,
        allowed_models=list(dict.fromkeys(allowed_models)),
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key, raw


async def revoke_api_key(db: AsyncSession, *, user: User, key_id: str) -> ApiKey:
    key = await db.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id).with_for_update()
    )
    if not key:
        raise HTTPException(status_code=404, detail={"code": "API_KEY_NOT_FOUND"})
    key.status = "revoked"
    key.revoked_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(key)
    return key


async def _assert_can_afford(
    user: User,
    *,
    api_key: ApiKey | None,
    estimate_micros: int,
) -> None:
    if available_micros(user) < estimate_micros:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "INSUFFICIENT_BALANCE", "message": "余额不足，无法完成推理请求"},
        )
    if api_key and api_key.credit_limit_cents is not None:
        estimate_cents = (estimate_micros + 9_999) // 10_000
        if api_key.spent_cents + estimate_cents > api_key.credit_limit_cents:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={"code": "KEY_CREDIT_LIMIT", "message": "该 API Key 额度已用尽"},
            )


async def _load_existing_usage(db: AsyncSession, request_id: str) -> UsageEvent | None:
    return await db.scalar(select(UsageEvent).where(UsageEvent.request_id == request_id))


def _result_from_usage(existing: UsageEvent) -> GatewayResult:
    return GatewayResult(
        completion_id=f"chatcmpl_{existing.id}",
        model=existing.model_slug,
        content=existing.response_text or "",
        prompt_tokens=existing.prompt_tokens,
        completion_tokens=existing.completion_tokens,
        replica_label=existing.replica_label or "",
        usage_event_id=existing.id,
        debit_cents=existing.debit_cents,
        cost_micros=existing.cost_micros,
        latency_ms=existing.latency_ms,
        routed_model=existing.routed_model_slug,
        routing_tier=existing.routing_tier,
        routing_decision_source=existing.routing_decision_source,
        classifier_model=existing.classifier_model_slug,
        classifier_latency_ms=existing.classifier_latency_ms,
    )


async def run_chat_completion(
    db: AsyncSession,
    *,
    user: User,
    model_slug: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    request_id: str,
    temperature: float | None = None,
    api_key: ApiKey | None = None,
    conversation_id: str | None = None,
) -> GatewayResult:
    existing = await _load_existing_usage(db, request_id)
    if existing and existing.status == "succeeded":
        return _result_from_usage(existing)

    requested_model = await get_published_model(db, model_slug)
    if api_key and api_key.allowed_models and requested_model.slug not in api_key.allowed_models:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "KEY_MODEL_FORBIDDEN", "message": "该 API Key 无权调用此模型"},
        )
    if requested_model.backend_type != "auto_router" and not ordered_replicas(requested_model):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "NO_HEALTHY_REPLICA", "message": "模型暂无可用副本"},
        )

    prompt_estimate = estimate_prompt_tokens(messages)
    max_tokens = max(1, min(max_tokens, requested_model.context_length))
    estimate = estimate_max_cost_micros(
        prompt_tokens=prompt_estimate,
        max_completion_tokens=max_tokens,
        price_prompt_per_mtok_cents=requested_model.price_prompt_per_mtok_cents,
        price_completion_per_mtok_cents=requested_model.price_completion_per_mtok_cents,
    )
    locked_user = await db.get(User, user.id, with_for_update=True)
    if not locked_user or locked_user.status != "active":
        raise HTTPException(status_code=401, detail={"code": "ACCOUNT_UNAVAILABLE"})
    locked_key = None
    if api_key:
        locked_key = await db.get(ApiKey, api_key.id, with_for_update=True)
        if not locked_key or locked_key.status != "active":
            raise HTTPException(status_code=401, detail={"code": "API_KEY_INVALID"})

    # A concurrent request with the same ID may have completed while this request waited for the
    # account lock. Recheck before consuming limits, calling the upstream, or mutating the wallet.
    existing = await _load_existing_usage(db, request_id)
    if existing and existing.status == "succeeded":
        return _result_from_usage(existing)

    if locked_key:
        await consume_api_key_limit(
            locked_key,
            token_budget=prompt_estimate + max_tokens,
        )
    await _assert_can_afford(locked_user, api_key=locked_key, estimate_micros=estimate)

    started = time.perf_counter()
    route = await resolve_route(
        db,
        requested_model=requested_model,
        messages=messages,
        max_tokens=max_tokens,
    )
    execution_model = route.execution_model
    max_tokens = min(max_tokens, execution_model.context_length)
    replicas = ordered_replicas(execution_model)
    backend = backend_for_model(execution_model)
    last_error: InferenceBackendError | None = None
    result = None
    for replica in replicas:
        try:
            target = target_for_replica(execution_model, replica)
            result = await backend.chat_completions(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                target=target,
                fail_once=replica.fail_once,
            )
            if replica.fail_once:
                replica.fail_once = False
            break
        except InferenceBackendError as exc:
            last_error = exc
            continue

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": last_error.code if last_error else "INFERENCE_FAILED",
                "message": last_error.message if last_error else "全部副本失败",
            },
        )

    latency_ms = int((time.perf_counter() - started) * 1000)
    from app.services.wallet import cost_micros_for_tokens

    cost_micros = cost_micros_for_tokens(
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        price_prompt_per_mtok_cents=requested_model.price_prompt_per_mtok_cents,
        price_completion_per_mtok_cents=requested_model.price_completion_per_mtok_cents,
    )
    debit = settle_inference_micros(locked_user, cost_micros)
    if debit > 0:
        wallet_row = await debit_cents(
            db,
            user=locked_user,
            amount_cents=debit,
            transaction_type="inference_debit",
            idempotency_key=f"inference:{request_id}",
            description=f"Open Compute System · {requested_model.slug}",
        )
        if wallet_row is None:
            # Roll back remainder mutation by re-raising; rare race after estimate.
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={"code": "INSUFFICIENT_BALANCE", "message": "余额不足"},
            )
    if locked_key:
        locked_key.spent_cents += debit
        locked_key.last_used_at = datetime.now(UTC)

    usage = UsageEvent(
        request_id=request_id,
        user_id=locked_user.id,
        api_key_id=locked_key.id if locked_key else None,
        conversation_id=conversation_id,
        model_slug=requested_model.slug,
        routed_model_slug=(
            execution_model.slug if requested_model.backend_type == "auto_router" else None
        ),
        routing_tier=route.tier,
        routing_decision_source=route.decision_source,
        classifier_model_slug=route.classifier_model_slug,
        classifier_latency_ms=route.classifier_latency_ms,
        replica_label=result.replica_label,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        latency_ms=latency_ms,
        cost_micros=cost_micros,
        debit_cents=debit,
        status="succeeded",
        response_text=result.content,
    )
    db.add(usage)
    await db.commit()
    await db.refresh(usage)
    return GatewayResult(
        completion_id=f"chatcmpl_{usage.id}",
        model=requested_model.slug,
        content=result.content,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        replica_label=result.replica_label,
        usage_event_id=usage.id,
        debit_cents=debit,
        cost_micros=cost_micros,
        latency_ms=latency_ms,
        routed_model=(
            execution_model.slug if requested_model.backend_type == "auto_router" else None
        ),
        routing_tier=route.tier,
        routing_decision_source=route.decision_source,
        classifier_model=route.classifier_model_slug,
        classifier_latency_ms=route.classifier_latency_ms,
    )


async def stream_chat_completion(
    db: AsyncSession,
    *,
    user: User,
    model_slug: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    request_id: str,
    temperature: float | None = None,
    api_key: ApiKey | None = None,
    conversation_id: str | None = None,
) -> AsyncIterator[str]:
    """Bill once via the non-stream path, then emit OpenAI-compatible SSE chunks."""
    import asyncio
    import json

    result = await run_chat_completion(
        db,
        user=user,
        model_slug=model_slug,
        messages=messages,
        max_tokens=max_tokens,
        request_id=request_id,
        temperature=temperature,
        api_key=api_key,
        conversation_id=conversation_id,
    )
    words = result.content.split(" ")
    for index, word in enumerate(words):
        piece = word if index == 0 else f" {word}"
        chunk = {
            "id": result.completion_id,
            "object": "chat.completion.chunk",
            "model": result.model,
            "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.01)
    final = {
        "id": result.completion_id,
        "object": "chat.completion.chunk",
        "model": result.model,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.prompt_tokens + result.completion_tokens,
        },
    }
    if result.routed_model:
        final["ocs_router"] = {
            "selected_model": result.routed_model,
            "tier": result.routing_tier,
            "decision_source": result.routing_decision_source,
        }
    yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


def openai_completion_payload(result: GatewayResult) -> dict[str, Any]:
    payload = {
        "id": result.completion_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": result.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result.content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.prompt_tokens + result.completion_tokens,
        },
    }
    if result.routed_model:
        payload["ocs_router"] = {
            "selected_model": result.routed_model,
            "tier": result.routing_tier,
            "decision_source": result.routing_decision_source,
        }
    return payload


def new_request_id(header_value: str | None = None) -> str:
    return header_value or f"req_{uuid.uuid4().hex}"
