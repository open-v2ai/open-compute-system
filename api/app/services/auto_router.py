from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AdminUser, AutoRouterConfig, InferenceModel
from app.schemas import AutoRouterConfigRequest
from app.services.audit import add_audit


async def _load_direct_models(
    db: AsyncSession,
    *,
    model_ids: set[str],
) -> dict[str, InferenceModel]:
    rows = list(
        (
            await db.scalars(
                select(InferenceModel)
                .where(InferenceModel.id.in_(model_ids))
                .options(selectinload(InferenceModel.replicas))
            )
        ).all()
    )
    by_id = {model.id: model for model in rows}
    if set(by_id) != model_ids:
        raise HTTPException(status_code=422, detail={"code": "ROUTER_MODEL_NOT_FOUND"})
    for model in rows:
        if model.backend_type == "auto_router":
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "NESTED_AUTO_ROUTER_FORBIDDEN",
                    "message": "Auto Router 不能把另一个 Auto Router 作为内部模型",
                },
            )
        if model.status != "published":
            raise HTTPException(
                status_code=422,
                detail={"code": "ROUTER_TARGET_NOT_PUBLISHED", "model_id": model.id},
            )
        if not any(
            replica.enabled and replica.health_status == "healthy"
            for replica in model.replicas
        ):
            raise HTTPException(
                status_code=422,
                detail={"code": "ROUTER_TARGET_UNAVAILABLE", "model_id": model.id},
            )
    return by_id


async def validate_auto_router_ready(
    db: AsyncSession,
    *,
    model: InferenceModel,
) -> AutoRouterConfig:
    config = await db.scalar(
        select(AutoRouterConfig).where(AutoRouterConfig.virtual_model_id == model.id)
    )
    if not config:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "AUTO_ROUTER_NOT_CONFIGURED",
                "message": "请先配置判断模型、简单模型和复杂模型",
            },
        )
    await _load_direct_models(
        db,
        model_ids={
            config.classifier_model_id,
            config.simple_model_id,
            config.complex_model_id,
        },
    )
    return config


async def configure_auto_router(
    db: AsyncSession,
    *,
    model_id: str,
    payload: AutoRouterConfigRequest,
    admin: AdminUser,
    request_id: str | None,
) -> AutoRouterConfig:
    model = await db.get(InferenceModel, model_id, with_for_update=True)
    if not model:
        raise HTTPException(status_code=404, detail={"code": "INFERENCE_MODEL_NOT_FOUND"})
    if model.backend_type != "auto_router":
        raise HTTPException(status_code=422, detail={"code": "MODEL_IS_NOT_AUTO_ROUTER"})
    if payload.simple_model_id == payload.complex_model_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "ROUTER_TIERS_MUST_DIFFER",
                "message": "简单模型和复杂模型必须不同",
            },
        )
    target_ids = {
        payload.classifier_model_id,
        payload.simple_model_id,
        payload.complex_model_id,
    }
    if model.id in target_ids:
        raise HTTPException(status_code=422, detail={"code": "AUTO_ROUTER_CYCLE"})
    await _load_direct_models(db, model_ids=target_ids)

    config = await db.scalar(
        select(AutoRouterConfig)
        .where(AutoRouterConfig.virtual_model_id == model.id)
        .with_for_update()
    )
    if config:
        if payload.version is None or config.version != payload.version:
            raise HTTPException(status_code=409, detail={"code": "VERSION_CONFLICT"})
        before = {
            "classifier_model_id": config.classifier_model_id,
            "simple_model_id": config.simple_model_id,
            "complex_model_id": config.complex_model_id,
            "fallback_tier": config.fallback_tier,
        }
        config.classifier_model_id = payload.classifier_model_id
        config.simple_model_id = payload.simple_model_id
        config.complex_model_id = payload.complex_model_id
        config.fallback_tier = payload.fallback_tier
        config.classifier_timeout_seconds = payload.classifier_timeout_seconds
        config.version += 1
    else:
        if payload.version is not None:
            raise HTTPException(status_code=409, detail={"code": "VERSION_CONFLICT"})
        before = None
        config = AutoRouterConfig(
            virtual_model_id=model.id,
            classifier_model_id=payload.classifier_model_id,
            simple_model_id=payload.simple_model_id,
            complex_model_id=payload.complex_model_id,
            fallback_tier=payload.fallback_tier,
            classifier_timeout_seconds=payload.classifier_timeout_seconds,
        )
        db.add(config)

    await db.flush()
    add_audit(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action="auto_router.configured",
        object_type="auto_router_config",
        object_id=config.id,
        summary={
            "virtual_model_id": model.id,
            "before": before,
            "after": {
                "classifier_model_id": config.classifier_model_id,
                "simple_model_id": config.simple_model_id,
                "complex_model_id": config.complex_model_id,
                "fallback_tier": config.fallback_tier,
                "classifier_timeout_seconds": config.classifier_timeout_seconds,
            },
        },
        request_id=request_id,
    )
    await db.commit()
    await db.refresh(config)
    return config
