from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AdminUser, InferenceModel, InferenceReplica
from app.schemas import (
    InferenceModelCreateRequest,
    InferenceReplicaCreateRequest,
    InferenceReplicaUpdateRequest,
)
from app.services.audit import add_audit
from app.services.gateway import backend_for_model, target_for_replica


def _validate_margin(
    *,
    price_prompt: int,
    price_completion: int,
    cost_prompt: int,
    cost_completion: int,
) -> None:
    if price_prompt <= cost_prompt or price_completion <= cost_completion:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_MARGIN", "message": "销售价必须高于供应成本"},
        )


def _validate_endpoint(backend_type: str, endpoint: str) -> str:
    value = endpoint.strip().rstrip("/")
    parsed = urlparse(value)
    if backend_type == "mock":
        if parsed.scheme != "mock":
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_REPLICA_ENDPOINT",
                    "message": "Mock 模型需要 mock:// 端点",
                },
            )
        return value
    if backend_type != "openai_compatible":
        raise HTTPException(status_code=422, detail={"code": "BACKEND_UNSUPPORTED"})
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_REPLICA_ENDPOINT",
                "message": "端点必须是无内嵌凭据、查询参数或片段的 HTTP(S) base URL",
            },
        )
    if value.endswith("/chat/completions"):
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_REPLICA_ENDPOINT", "message": "请填写 API base URL"},
        )
    return value


async def create_model(
    db: AsyncSession,
    *,
    payload: InferenceModelCreateRequest,
    admin: AdminUser,
    request_id: str | None,
) -> InferenceModel:
    existing = await db.scalar(select(InferenceModel.id).where(InferenceModel.slug == payload.slug))
    if existing:
        raise HTTPException(status_code=409, detail={"code": "MODEL_SLUG_EXISTS"})
    _validate_margin(
        price_prompt=payload.price_prompt_per_mtok_cents,
        price_completion=payload.price_completion_per_mtok_cents,
        cost_prompt=payload.cost_prompt_per_mtok_cents,
        cost_completion=payload.cost_completion_per_mtok_cents,
    )
    model = InferenceModel(**payload.model_dump())
    db.add(model)
    await db.flush()
    add_audit(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action="inference_model.created",
        object_type="inference_model",
        object_id=model.id,
        summary={"slug": model.slug, "backend_type": model.backend_type},
        request_id=request_id,
    )
    await db.commit()
    await db.refresh(model)
    return model


async def create_replica(
    db: AsyncSession,
    *,
    model_id: str,
    payload: InferenceReplicaCreateRequest,
    admin: AdminUser,
    request_id: str | None,
) -> InferenceReplica:
    model = await db.get(InferenceModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail={"code": "INFERENCE_MODEL_NOT_FOUND"})
    if model.backend_type == "auto_router":
        raise HTTPException(
            status_code=422,
            detail={
                "code": "AUTO_ROUTER_HAS_NO_REPLICAS",
                "message": "Auto Router 通过路由配置引用内部模型，不直接添加副本",
            },
        )
    existing = await db.scalar(
        select(InferenceReplica.id).where(
            InferenceReplica.model_id == model.id,
            InferenceReplica.label == payload.label,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail={"code": "REPLICA_LABEL_EXISTS"})
    values = payload.model_dump()
    values["endpoint"] = _validate_endpoint(model.backend_type, payload.endpoint)
    replica = InferenceReplica(
        model_id=model.id,
        health_status="unknown",
        **values,
    )
    db.add(replica)
    await db.flush()
    add_audit(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action="inference_replica.created",
        object_type="inference_replica",
        object_id=replica.id,
        summary={"model_id": model.id, "label": replica.label},
        request_id=request_id,
    )
    await db.commit()
    await db.refresh(replica)
    return replica


async def update_replica(
    db: AsyncSession,
    *,
    replica_id: str,
    payload: InferenceReplicaUpdateRequest,
    admin: AdminUser,
    request_id: str | None,
) -> InferenceReplica:
    replica = await db.scalar(
        select(InferenceReplica)
        .where(InferenceReplica.id == replica_id)
        .options(selectinload(InferenceReplica.model))
        .with_for_update()
    )
    if not replica:
        raise HTTPException(status_code=404, detail={"code": "INFERENCE_REPLICA_NOT_FOUND"})
    if replica.version != payload.version:
        raise HTTPException(status_code=409, detail={"code": "VERSION_CONFLICT"})
    changes = payload.model_dump(exclude={"version"}, exclude_none=True)
    if "endpoint" in changes:
        changes["endpoint"] = _validate_endpoint(replica.model.backend_type, changes["endpoint"])
    before = {
        "endpoint": replica.endpoint,
        "upstream_model": replica.upstream_model,
        "enabled": replica.enabled,
    }
    connectivity_fields = {"endpoint", "upstream_model", "credential_env_var", "timeout_seconds"}
    if connectivity_fields.intersection(changes):
        replica.health_status = "unknown"
    for field, value in changes.items():
        setattr(replica, field, value)
    replica.version += 1
    add_audit(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action="inference_replica.updated",
        object_type="inference_replica",
        object_id=replica.id,
        summary={"before": before, "after": changes},
        request_id=request_id,
    )
    await db.commit()
    await db.refresh(replica)
    return replica


async def check_replica_health(
    db: AsyncSession,
    *,
    replica_id: str,
    admin: AdminUser,
    request_id: str | None,
) -> InferenceReplica:
    replica = await db.scalar(
        select(InferenceReplica)
        .where(InferenceReplica.id == replica_id)
        .options(selectinload(InferenceReplica.model))
        .with_for_update()
    )
    if not replica:
        raise HTTPException(status_code=404, detail={"code": "INFERENCE_REPLICA_NOT_FOUND"})
    try:
        target = target_for_replica(replica.model, replica)
        healthy = await backend_for_model(replica.model).health_check(target)
    except Exception:
        healthy = False
    replica.health_status = "healthy" if healthy else "unhealthy"
    replica.last_health_checked_at = datetime.now(UTC)
    replica.version += 1
    add_audit(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action="inference_replica.health_checked",
        object_type="inference_replica",
        object_id=replica.id,
        summary={"health_status": replica.health_status},
        request_id=request_id,
    )
    await db.commit()
    await db.refresh(replica)
    return replica
