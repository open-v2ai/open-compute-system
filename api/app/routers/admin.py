from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.identity import mask_email
from app.core.permissions import has_permissions, require_permissions
from app.core.security import mask_phone
from app.db.session import get_db
from app.models import (
    SKU,
    AdminUser,
    AuditLog,
    AutoRouterConfig,
    InferenceDeployment,
    InferenceModel,
    InferenceNode,
    InferenceReplica,
    Instance,
    InstanceTask,
    Order,
    PriceVersion,
    ResourceProvider,
    UsageEvent,
    User,
)
from app.schemas import (
    AdminInferenceModelResponse,
    AdminInferenceReplicaResponse,
    AdminInstanceResponse,
    AdminOrderResponse,
    AdminSKUResponse,
    AdminUserResponse,
    AuditResponse,
    AutoRouterConfigRequest,
    AutoRouterConfigResponse,
    DashboardResponse,
    InferenceDeploymentCreateRequest,
    InferenceDeploymentResponse,
    InferenceModelCreateRequest,
    InferenceModelResponse,
    InferenceModelUpdateRequest,
    InferenceNodeCreateRequest,
    InferenceNodeResponse,
    InferenceReplicaCreateRequest,
    InferenceReplicaUpdateRequest,
    ProviderResponse,
    SKUCreateRequest,
    SKUUpdateRequest,
    TaskResponse,
    UsageEventResponse,
)
from app.services.audit import add_audit
from app.services.auto_router import configure_auto_router, validate_auto_router_ready
from app.services.inference_catalog import (
    check_replica_health,
    create_model,
    create_replica,
    update_replica,
)
from app.services.inference_deployments import (
    check_node_health,
    create_deployment,
    create_node,
    stop_deployment,
    sync_deployment,
)
from app.services.instances import retry_failed_task

router = APIRouter(prefix="/admin", tags=["admin"])


def masked_contact(user: User) -> str:
    if user.phone is not None:
        return mask_phone(user.phone)
    return mask_email(user.email or "")


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    _: AdminUser = Depends(require_permissions("dashboard.read")),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    users = await db.scalar(select(func.count(User.id))) or 0
    running = await db.scalar(
        select(func.count(Instance.id)).where(Instance.status == "running")
    ) or 0
    failed = await db.scalar(
        select(func.count(InstanceTask.id)).where(
            InstanceTask.status.in_(["failed", "manual_review"])
        )
    ) or 0
    inventory = await db.scalar(select(func.sum(SKU.inventory_available))) or 0
    orders = await db.scalar(select(func.count(Order.id))) or 0
    sales = await db.scalar(
        select(func.sum(Order.amount_cents)).where(Order.status == "fulfilled")
    ) or 0
    published_models = await db.scalar(
        select(func.count(InferenceModel.id)).where(InferenceModel.status == "published")
    ) or 0
    healthy_replicas = await db.scalar(
        select(func.count(InferenceReplica.id)).where(
            InferenceReplica.enabled.is_(True),
            InferenceReplica.health_status == "healthy",
        )
    ) or 0
    inference_requests = await db.scalar(
        select(func.count(UsageEvent.id)).where(UsageEvent.status == "succeeded")
    ) or 0
    inference_tokens = await db.scalar(
        select(func.sum(UsageEvent.prompt_tokens + UsageEvent.completion_tokens)).where(
            UsageEvent.status == "succeeded"
        )
    ) or 0
    inference_revenue = await db.scalar(
        select(func.sum(UsageEvent.debit_cents)).where(UsageEvent.status == "succeeded")
    ) or 0
    return DashboardResponse(
        users=users,
        running_instances=running,
        failed_tasks=failed,
        available_inventory=inventory,
        orders=orders,
        sales_cents=sales,
        published_models=published_models,
        healthy_replicas=healthy_replicas,
        inference_requests=inference_requests,
        inference_tokens=inference_tokens,
        inference_revenue_cents=inference_revenue,
    )


@router.get("/providers", response_model=list[ProviderResponse])
async def providers(
    _: AdminUser = Depends(require_permissions("providers.read")),
    db: AsyncSession = Depends(get_db),
) -> list[ResourceProvider]:
    return list((await db.scalars(select(ResourceProvider))).all())


@router.get("/skus", response_model=list[AdminSKUResponse])
async def skus(
    admin: AdminUser = Depends(require_permissions("catalog.read")),
    db: AsyncSession = Depends(get_db),
) -> list[AdminSKUResponse]:
    rows = list((await db.scalars(select(SKU).order_by(SKU.created_at.desc()))).all())
    can_read_cost = has_permissions(admin, {"catalog.cost.read"})
    return [
        AdminSKUResponse.model_validate(sku).model_copy(
            update={"cost_hour_cents": sku.cost_hour_cents if can_read_cost else None}
        )
        for sku in rows
    ]


@router.post("/skus", response_model=AdminSKUResponse, status_code=201)
async def create_sku(
    payload: SKUCreateRequest,
    request: Request,
    admin: AdminUser = Depends(require_permissions("catalog.manage")),
    db: AsyncSession = Depends(get_db),
) -> SKU:
    provider = await db.scalar(select(ResourceProvider).where(ResourceProvider.enabled.is_(True)))
    sku = SKU(
        provider_id=provider.id if provider else None,
        inventory_available=payload.inventory_total,
        inventory_reserved=0,
        status="draft",
        **payload.model_dump(),
    )
    db.add(sku)
    await db.flush()
    db.add(
        PriceVersion(
            sku_id=sku.id,
            price_hour_cents=sku.price_hour_cents,
            price_day_cents=sku.price_day_cents,
            price_week_cents=sku.price_week_cents,
            price_month_cents=sku.price_month_cents,
            cost_hour_cents=sku.cost_hour_cents,
            created_by=admin.id,
        )
    )
    add_audit(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action="sku.created",
        object_type="sku",
        object_id=sku.id,
        summary={"name": sku.name, "status": sku.status},
        request_id=request.state.request_id,
    )
    await db.commit()
    await db.refresh(sku)
    return sku


@router.patch("/skus/{sku_id}", response_model=AdminSKUResponse)
async def update_sku(
    sku_id: str,
    payload: SKUUpdateRequest,
    request: Request,
    admin: AdminUser = Depends(require_permissions("catalog.manage")),
    db: AsyncSession = Depends(get_db),
) -> SKU:
    sku = await db.get(SKU, sku_id, with_for_update=True)
    if not sku:
        raise HTTPException(status_code=404, detail={"code": "SKU_NOT_FOUND"})
    if sku.version != payload.version:
        raise HTTPException(
            status_code=409,
            detail={"code": "VERSION_CONFLICT", "message": "商品已被其他管理员修改，请刷新"},
        )
    before = {"status": sku.status, "price_hour_cents": sku.price_hour_cents}
    changed_price = False
    changes = payload.model_dump(exclude={"version", "reason"}, exclude_none=True)
    for field, value in changes.items():
        if field == "inventory_total":
            allocated = sku.inventory_total - sku.inventory_available - sku.inventory_reserved
            if value < allocated:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "INVENTORY_BELOW_ALLOCATED",
                        "message": "总库存不能小于已分配量",
                    },
                )
            sku.inventory_available = value - allocated - sku.inventory_reserved
        if field.startswith("price_") or field == "cost_hour_cents":
            changed_price = True
        setattr(sku, field, value)
    if sku.status == "published" and sku.price_hour_cents <= sku.cost_hour_cents:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_MARGIN", "message": "上架销售价必须高于供应成本"},
        )
    sku.version += 1
    if changed_price:
        db.add(
            PriceVersion(
                sku_id=sku.id,
                price_hour_cents=sku.price_hour_cents,
                price_day_cents=sku.price_day_cents,
                price_week_cents=sku.price_week_cents,
                price_month_cents=sku.price_month_cents,
                cost_hour_cents=sku.cost_hour_cents,
                reason=payload.reason,
                created_by=admin.id,
            )
        )
    add_audit(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action="sku.updated",
        object_type="sku",
        object_id=sku.id,
        summary={"before": before, "after": {"status": sku.status, "version": sku.version}},
        request_id=request.state.request_id,
    )
    await db.commit()
    await db.refresh(sku)
    return sku


@router.get("/instances", response_model=list[AdminInstanceResponse])
async def instances(
    _: AdminUser = Depends(require_permissions("instances.read")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    rows = (
        await db.execute(
            select(Instance, User, SKU)
            .join(User, User.id == Instance.user_id)
            .join(SKU, SKU.id == Instance.sku_id)
            .order_by(Instance.created_at.desc())
        )
    ).all()
    return [
        {
            "id": instance.id,
            "name": instance.name,
            "user": user.nickname,
            "user_id": user.id,
            "contact": masked_contact(user),
            "sku": sku.name,
            "region": sku.region,
            "status": instance.status,
            "created_at": instance.created_at,
        }
        for instance, user, sku in rows
    ]


@router.get("/tasks", response_model=list[TaskResponse])
async def tasks(
    _: AdminUser = Depends(require_permissions("tasks.read")),
    db: AsyncSession = Depends(get_db),
) -> list[InstanceTask]:
    return list(
        (await db.scalars(select(InstanceTask).order_by(InstanceTask.created_at.desc()))).all()
    )


@router.post("/tasks/{task_id}/retry", response_model=TaskResponse)
async def retry_task(
    task_id: str,
    request: Request,
    admin: AdminUser = Depends(require_permissions("tasks.manage")),
    db: AsyncSession = Depends(get_db),
) -> InstanceTask:
    return await retry_failed_task(
        db,
        task_id=task_id,
        admin_id=admin.id,
        request_id=request.state.request_id,
    )


@router.get("/users", response_model=list[AdminUserResponse])
async def users(
    admin: AdminUser = Depends(require_permissions("users.read")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    rows = list((await db.scalars(select(User).order_by(User.created_at.desc()))).all())
    can_read_balance = has_permissions(admin, {"users.balance.read"})
    return [
        {
            "id": user.id,
            "nickname": user.nickname,
            "phone": mask_phone(user.phone) if user.phone else None,
            "email": mask_email(user.email) if user.email else None,
            "real_name_status": user.real_name_status,
            "balance_cents": user.balance_cents if can_read_balance else None,
            "status": user.status,
            "created_at": user.created_at,
        }
        for user in rows
    ]


@router.get("/orders", response_model=list[AdminOrderResponse])
async def orders(
    _: AdminUser = Depends(require_permissions("orders.read")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    rows = (
        await db.execute(
            select(Order, User, SKU)
            .join(User, User.id == Order.user_id)
            .join(SKU, SKU.id == Order.sku_id)
            .order_by(Order.created_at.desc())
        )
    ).all()
    return [
        {
            "id": order.id,
            "user": user.nickname,
            "user_id": user.id,
            "contact": masked_contact(user),
            "sku": sku.name,
            "billing_mode": order.billing_mode,
            "amount_cents": order.amount_cents,
            "status": order.status,
            "created_at": order.created_at,
        }
        for order, user, sku in rows
    ]


@router.get("/audit-logs", response_model=list[AuditResponse])
async def audit_logs(
    _: AdminUser = Depends(require_permissions("audit.read")),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLog]:
    return list(
        (await db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200))).all()
    )


@router.get("/inference/models", response_model=list[AdminInferenceModelResponse])
async def inference_models(
    admin: AdminUser = Depends(require_permissions("inference.read")),
    db: AsyncSession = Depends(get_db),
) -> list[AdminInferenceModelResponse]:

    rows = list(
        (
            await db.scalars(
                select(InferenceModel)
                .options(selectinload(InferenceModel.router_config))
                .order_by(InferenceModel.slug.asc())
            )
        ).all()
    )
    can_read_cost = has_permissions(admin, {"inference.cost.read"})
    result: list[AdminInferenceModelResponse] = []
    for model in rows:
        count = await db.scalar(
            select(func.count(InferenceReplica.id)).where(InferenceReplica.model_id == model.id)
        )
        result.append(
            AdminInferenceModelResponse(
                id=model.id,
                slug=model.slug,
                display_name=model.display_name,
                description=model.description,
                context_length=model.context_length,
                price_prompt_per_mtok_cents=model.price_prompt_per_mtok_cents,
                price_completion_per_mtok_cents=model.price_completion_per_mtok_cents,
                status=model.status,
                version=model.version,
                is_auto_router=model.is_auto_router,
                cost_prompt_per_mtok_cents=(
                    model.cost_prompt_per_mtok_cents if can_read_cost else None
                ),
                cost_completion_per_mtok_cents=(
                    model.cost_completion_per_mtok_cents if can_read_cost else None
                ),
                backend_type=model.backend_type,
                replica_count=count or 0,
                router_config=model.router_config,
            )
        )
    return result


@router.get("/inference/nodes", response_model=list[InferenceNodeResponse])
async def inference_nodes(
    _: AdminUser = Depends(require_permissions("inference.read")),
    db: AsyncSession = Depends(get_db),
) -> list[InferenceNode]:
    return list(
        (await db.scalars(select(InferenceNode).order_by(InferenceNode.name.asc()))).all()
    )


@router.post(
    "/inference/nodes",
    response_model=InferenceNodeResponse,
    status_code=201,
)
async def create_inference_node(
    payload: InferenceNodeCreateRequest,
    request: Request,
    admin: AdminUser = Depends(require_permissions("inference.manage")),
    db: AsyncSession = Depends(get_db),
) -> InferenceNode:
    return await create_node(
        db,
        payload=payload,
        admin=admin,
        request_id=request.state.request_id,
    )


@router.post(
    "/inference/nodes/{node_id}/health-check",
    response_model=InferenceNodeResponse,
)
async def health_check_inference_node(
    node_id: str,
    request: Request,
    admin: AdminUser = Depends(require_permissions("inference.manage")),
    db: AsyncSession = Depends(get_db),
) -> InferenceNode:
    return await check_node_health(
        db,
        node_id=node_id,
        admin=admin,
        request_id=request.state.request_id,
    )


@router.get(
    "/inference/deployments",
    response_model=list[InferenceDeploymentResponse],
)
async def inference_deployments(
    _: AdminUser = Depends(require_permissions("inference.read")),
    db: AsyncSession = Depends(get_db),
) -> list[InferenceDeployment]:
    return list(
        (
            await db.scalars(
                select(InferenceDeployment).order_by(InferenceDeployment.created_at.desc())
            )
        ).all()
    )


@router.post(
    "/inference/deployments",
    response_model=InferenceDeploymentResponse,
    status_code=202,
)
async def create_inference_deployment(
    payload: InferenceDeploymentCreateRequest,
    request: Request,
    idempotency_key: str = Header(
        min_length=8,
        max_length=128,
        alias="Idempotency-Key",
    ),
    admin: AdminUser = Depends(require_permissions("inference.manage")),
    db: AsyncSession = Depends(get_db),
) -> InferenceDeployment:
    return await create_deployment(
        db,
        payload=payload,
        idempotency_key=idempotency_key,
        admin=admin,
        request_id=request.state.request_id,
    )


@router.post(
    "/inference/deployments/{deployment_id}/sync",
    response_model=InferenceDeploymentResponse,
)
async def sync_inference_deployment(
    deployment_id: str,
    request: Request,
    admin: AdminUser = Depends(require_permissions("inference.manage")),
    db: AsyncSession = Depends(get_db),
) -> InferenceDeployment:
    return await sync_deployment(
        db,
        deployment_id=deployment_id,
        admin=admin,
        request_id=request.state.request_id,
    )


@router.post(
    "/inference/deployments/{deployment_id}/stop",
    response_model=InferenceDeploymentResponse,
)
async def stop_inference_deployment(
    deployment_id: str,
    request: Request,
    admin: AdminUser = Depends(require_permissions("inference.manage")),
    db: AsyncSession = Depends(get_db),
) -> InferenceDeployment:
    return await stop_deployment(
        db,
        deployment_id=deployment_id,
        admin=admin,
        request_id=request.state.request_id,
    )


@router.post(
    "/inference/models",
    response_model=AdminInferenceModelResponse,
    status_code=201,
)
async def create_inference_model(
    payload: InferenceModelCreateRequest,
    request: Request,
    admin: AdminUser = Depends(require_permissions("inference.manage")),
    db: AsyncSession = Depends(get_db),
) -> AdminInferenceModelResponse:
    model = await create_model(
        db,
        payload=payload,
        admin=admin,
        request_id=request.state.request_id,
    )
    can_read_cost = has_permissions(admin, {"inference.cost.read"})
    return AdminInferenceModelResponse(
        **InferenceModelResponse.model_validate(model).model_dump(),
        cost_prompt_per_mtok_cents=(
            model.cost_prompt_per_mtok_cents if can_read_cost else None
        ),
        cost_completion_per_mtok_cents=(
            model.cost_completion_per_mtok_cents if can_read_cost else None
        ),
        backend_type=model.backend_type,
        replica_count=0,
        router_config=None,
    )


@router.put(
    "/inference/models/{model_id}/auto-router",
    response_model=AutoRouterConfigResponse,
)
async def put_auto_router_config(
    model_id: str,
    payload: AutoRouterConfigRequest,
    request: Request,
    admin: AdminUser = Depends(require_permissions("inference.manage")),
    db: AsyncSession = Depends(get_db),
) -> AutoRouterConfig:
    return await configure_auto_router(
        db,
        model_id=model_id,
        payload=payload,
        admin=admin,
        request_id=request.state.request_id,
    )


@router.get(
    "/inference/models/{model_id}/replicas",
    response_model=list[AdminInferenceReplicaResponse],
)
async def inference_replicas(
    model_id: str,
    _: AdminUser = Depends(require_permissions("inference.read")),
    db: AsyncSession = Depends(get_db),
) -> list[InferenceReplica]:
    model = await db.get(InferenceModel, model_id)
    if not model:
        raise HTTPException(status_code=404, detail={"code": "INFERENCE_MODEL_NOT_FOUND"})
    return list(
        (
            await db.scalars(
                select(InferenceReplica)
                .where(InferenceReplica.model_id == model_id)
                .order_by(InferenceReplica.weight.desc(), InferenceReplica.label.asc())
            )
        ).all()
    )


@router.post(
    "/inference/models/{model_id}/replicas",
    response_model=AdminInferenceReplicaResponse,
    status_code=201,
)
async def create_inference_replica(
    model_id: str,
    payload: InferenceReplicaCreateRequest,
    request: Request,
    admin: AdminUser = Depends(require_permissions("inference.manage")),
    db: AsyncSession = Depends(get_db),
) -> InferenceReplica:
    return await create_replica(
        db,
        model_id=model_id,
        payload=payload,
        admin=admin,
        request_id=request.state.request_id,
    )


@router.patch(
    "/inference/replicas/{replica_id}",
    response_model=AdminInferenceReplicaResponse,
)
async def patch_inference_replica(
    replica_id: str,
    payload: InferenceReplicaUpdateRequest,
    request: Request,
    admin: AdminUser = Depends(require_permissions("inference.manage")),
    db: AsyncSession = Depends(get_db),
) -> InferenceReplica:
    return await update_replica(
        db,
        replica_id=replica_id,
        payload=payload,
        admin=admin,
        request_id=request.state.request_id,
    )


@router.post(
    "/inference/replicas/{replica_id}/health-check",
    response_model=AdminInferenceReplicaResponse,
)
async def health_check_inference_replica(
    replica_id: str,
    request: Request,
    admin: AdminUser = Depends(require_permissions("inference.manage")),
    db: AsyncSession = Depends(get_db),
) -> InferenceReplica:
    return await check_replica_health(
        db,
        replica_id=replica_id,
        admin=admin,
        request_id=request.state.request_id,
    )


@router.patch("/inference/models/{model_id}", response_model=AdminInferenceModelResponse)
async def update_inference_model(
    model_id: str,
    payload: InferenceModelUpdateRequest,
    request: Request,
    admin: AdminUser = Depends(require_permissions("inference.manage")),
    db: AsyncSession = Depends(get_db),
) -> AdminInferenceModelResponse:

    model = await db.get(InferenceModel, model_id, with_for_update=True)
    if not model:
        raise HTTPException(status_code=404, detail={"code": "INFERENCE_MODEL_NOT_FOUND"})
    if model.version != payload.version:
        raise HTTPException(
            status_code=409,
            detail={"code": "VERSION_CONFLICT", "message": "模型已被其他管理员修改，请刷新"},
        )
    before = {
        "status": model.status,
        "price_prompt_per_mtok_cents": model.price_prompt_per_mtok_cents,
        "price_completion_per_mtok_cents": model.price_completion_per_mtok_cents,
    }
    changes = payload.model_dump(exclude={"version", "reason"}, exclude_none=True)
    for field, value in changes.items():
        setattr(model, field, value)
    if model.status == "published" and model.backend_type == "auto_router":
        await validate_auto_router_ready(db, model=model)
    elif model.status == "published":
        healthy_count = await db.scalar(
            select(func.count(InferenceReplica.id)).where(
                InferenceReplica.model_id == model.id,
                InferenceReplica.enabled.is_(True),
                InferenceReplica.health_status == "healthy",
            )
        )
        if not healthy_count:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "NO_HEALTHY_REPLICA",
                    "message": "模型至少需要一个已通过健康检查的启用副本才能上架",
                },
            )
    if model.status == "published" and (
        model.price_prompt_per_mtok_cents <= model.cost_prompt_per_mtok_cents
        or model.price_completion_per_mtok_cents <= model.cost_completion_per_mtok_cents
    ):
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_MARGIN", "message": "上架销售价必须高于供应成本"},
        )
    model.version += 1
    add_audit(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action="inference_model.updated",
        object_type="inference_model",
        object_id=model.id,
        summary={
            "before": before,
            "after": {"status": model.status, "version": model.version},
            "reason": payload.reason,
        },
        request_id=request.state.request_id,
    )
    await db.commit()
    await db.refresh(model)
    can_read_cost = has_permissions(admin, {"inference.cost.read"})
    count = await db.scalar(
        select(func.count(InferenceReplica.id)).where(InferenceReplica.model_id == model.id)
    )
    return AdminInferenceModelResponse(
        id=model.id,
        slug=model.slug,
        display_name=model.display_name,
        description=model.description,
        context_length=model.context_length,
        price_prompt_per_mtok_cents=model.price_prompt_per_mtok_cents,
        price_completion_per_mtok_cents=model.price_completion_per_mtok_cents,
        status=model.status,
        version=model.version,
        is_auto_router=model.is_auto_router,
        cost_prompt_per_mtok_cents=model.cost_prompt_per_mtok_cents if can_read_cost else None,
        cost_completion_per_mtok_cents=(
            model.cost_completion_per_mtok_cents if can_read_cost else None
        ),
        backend_type=model.backend_type,
        replica_count=count or 0,
        router_config=await db.scalar(
            select(AutoRouterConfig).where(AutoRouterConfig.virtual_model_id == model.id)
        ),
    )


@router.get("/inference/usage", response_model=list[UsageEventResponse])
async def inference_usage(
    _: AdminUser = Depends(require_permissions("inference.read")),
    db: AsyncSession = Depends(get_db),
) -> list[UsageEvent]:
    return list(
        (
            await db.scalars(select(UsageEvent).order_by(UsageEvent.created_at.desc()).limit(200))
        ).all()
    )
