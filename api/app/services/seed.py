from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import (
    SKU,
    AdminUser,
    AutoRouterConfig,
    InferenceModel,
    InferenceReplica,
    PriceVersion,
    ResourceProvider,
    User,
)

SKU_FIXTURES = [
    {
        "name": "RTX 4090 创作加速",
        "gpu_model": "RTX 4090",
        "gpu_memory_gb": 24,
        "gpu_count": 1,
        "vcpu": 16,
        "memory_gb": 64,
        "region": "华东·上海",
        "zone": "A 区",
        "price_hour_cents": 248,
        "price_day_cents": 5_200,
        "price_week_cents": 32_000,
        "price_month_cents": 118_000,
        "cost_hour_cents": 172,
        "inventory_total": 18,
        "inventory_available": 12,
        "inventory_reserved": 0,
        "status": "published",
        "tag": "性价比",
        "recommended": True,
    },
    {
        "name": "A100 80G 训练实例",
        "gpu_model": "A100",
        "gpu_memory_gb": 80,
        "gpu_count": 1,
        "vcpu": 24,
        "memory_gb": 120,
        "region": "华北·北京",
        "zone": "B 区",
        "price_hour_cents": 699,
        "price_day_cents": 14_800,
        "price_week_cents": 92_000,
        "price_month_cents": 338_000,
        "cost_hour_cents": 516,
        "inventory_total": 8,
        "inventory_available": 3,
        "inventory_reserved": 0,
        "status": "published",
        "tag": "热门",
        "recommended": True,
    },
    {
        "name": "H20 96G 推理实例",
        "gpu_model": "H20",
        "gpu_memory_gb": 96,
        "gpu_count": 2,
        "vcpu": 48,
        "memory_gb": 240,
        "region": "华南·深圳",
        "zone": "A 区",
        "price_hour_cents": 1_180,
        "price_day_cents": 24_500,
        "price_week_cents": 152_000,
        "price_month_cents": 558_000,
        "cost_hour_cents": 890,
        "inventory_total": 6,
        "inventory_available": 4,
        "inventory_reserved": 0,
        "status": "published",
        "tag": "推理优选",
        "recommended": False,
    },
    {
        "name": "L40S 48G 开发实例",
        "gpu_model": "L40S",
        "gpu_memory_gb": 48,
        "gpu_count": 1,
        "vcpu": 20,
        "memory_gb": 96,
        "region": "华东·杭州",
        "zone": "C 区",
        "price_hour_cents": 438,
        "price_day_cents": 9_200,
        "price_week_cents": 57_000,
        "price_month_cents": 208_000,
        "cost_hour_cents": 321,
        "inventory_total": 10,
        "inventory_available": 0,
        "inventory_reserved": 0,
        "status": "published",
        "tag": "到货提醒",
        "recommended": False,
    },
]


INFERENCE_MODEL_FIXTURES = [
    {
        "slug": "opencompute/qwen3-8b",
        "display_name": "Qwen3 8B",
        "description": "Open Compute System Mock · 轻量对话与开发调试",
        "context_length": 8192,
        "price_prompt_per_mtok_cents": 15,
        "price_completion_per_mtok_cents": 45,
        "cost_prompt_per_mtok_cents": 5,
        "cost_completion_per_mtok_cents": 15,
        "status": "published",
        "backend_type": "mock",
    },
    {
        "slug": "opencompute/qwen3-32b",
        "display_name": "Qwen3 32B",
        "description": "Open Compute System Mock · 长上下文与复杂任务",
        "context_length": 32768,
        "price_prompt_per_mtok_cents": 80,
        "price_completion_per_mtok_cents": 240,
        "cost_prompt_per_mtok_cents": 30,
        "cost_completion_per_mtok_cents": 90,
        "status": "published",
        "backend_type": "mock",
    },
    {
        "slug": "opencompute/auto",
        "display_name": "Auto Router",
        "description": "自动判断任务复杂度，并选择合适的模型提供服务",
        "context_length": 32768,
        "price_prompt_per_mtok_cents": 40,
        "price_completion_per_mtok_cents": 120,
        "cost_prompt_per_mtok_cents": 20,
        "cost_completion_per_mtok_cents": 60,
        "status": "published",
        "backend_type": "auto_router",
    },
]


async def seed_database(db: AsyncSession) -> None:
    if await db.scalar(select(func.count(User.id))) == 0:
        db.add(
            User(
                phone="13800138000",
                email="demo@opencompute.local",
                password_hash=hash_password("Demo12345"),
                nickname="Demo 用户",
                balance_cents=500_000,
            )
        )

    if await db.scalar(select(func.count(AdminUser.id))) == 0:
        db.add(
            AdminUser(
                username="admin",
                password_hash=hash_password("Admin12345"),
                display_name="平台管理员",
                role="super_admin",
                mfa_enabled=True,
            )
        )

    if await db.scalar(select(func.count(ResourceProvider.id))) == 0:
        provider = ResourceProvider(
            name="Open Compute System 演示资源池",
            provider_type="owned",
            access_mode="mock",
            region="全国",
            health_status="healthy",
        )
        db.add(provider)
        await db.flush()
        for fixture in SKU_FIXTURES:
            sku = SKU(provider_id=provider.id, **fixture)
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
                )
            )

    models_by_slug: dict[str, InferenceModel] = {}
    for fixture in INFERENCE_MODEL_FIXTURES:
        model = await db.scalar(
            select(InferenceModel).where(InferenceModel.slug == fixture["slug"])
        )
        if model is None:
            model = InferenceModel(**fixture)
            db.add(model)
            await db.flush()
            if model.backend_type != "auto_router":
                for label, weight, fail_once in (
                    ("mock-a", 100, False),
                    ("mock-b", 80, False),
                ):
                    db.add(
                        InferenceReplica(
                            model_id=model.id,
                            label=label,
                            endpoint=f"mock://{model.slug}/{label}",
                            weight=weight,
                            health_status="healthy",
                            enabled=True,
                            fail_once=fail_once,
                        )
                    )
        models_by_slug[model.slug] = model

    auto_model = models_by_slug["opencompute/auto"]
    auto_config = await db.scalar(
        select(AutoRouterConfig).where(AutoRouterConfig.virtual_model_id == auto_model.id)
    )
    if auto_config is None:
        small_model = models_by_slug["opencompute/qwen3-8b"]
        complex_model = models_by_slug["opencompute/qwen3-32b"]
        db.add(
            AutoRouterConfig(
                virtual_model_id=auto_model.id,
                classifier_model_id=small_model.id,
                simple_model_id=small_model.id,
                complex_model_id=complex_model.id,
                fallback_tier="complex",
                classifier_timeout_seconds=5,
            )
        )

    await db.commit()
