from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.middleware.observability import ObservabilityMiddleware, metrics_response
from app.middleware.security import CSRFMiddleware
from app.models import InferenceModel, ResourceProvider
from app.providers.factory import provider_for
from app.routers import admin, auth, instances, market, opencompute
from app.services.demo import require_mock_resources
from app.services.seed import seed_database

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.app_env == "test":
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    if settings.demo_seed_enabled:
        async with SessionLocal() as db:
            await seed_database(db)
    if settings.public_demo_enabled:
        async with SessionLocal() as db:
            await require_mock_resources(db)
    if settings.app_env == "production" and not settings.allow_mock_provider_in_production:
        async with SessionLocal() as db:
            mock_count = await db.scalar(
                select(func.count(ResourceProvider.id)).where(
                    ResourceProvider.enabled.is_(True), ResourceProvider.access_mode == "mock"
                )
            )
            if mock_count:
                raise RuntimeError("Enabled MockProvider resources are forbidden in production")
            mock_inference_count = await db.scalar(
                select(func.count(InferenceModel.id)).where(
                    InferenceModel.status == "published",
                    InferenceModel.backend_type == "mock",
                )
            )
            if mock_inference_count and not settings.allow_mock_inference_in_production:
                raise RuntimeError("Published Mock inference models are forbidden in production")
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.docs_enabled else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.docs_enabled else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Idempotency-Key",
        "X-CSRF-Token",
        "X-Request-ID",
        "Authorization",
    ],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(CSRFMiddleware)
app.add_middleware(ObservabilityMiddleware)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(market.router, prefix=settings.api_prefix)
app.include_router(instances.router, prefix=settings.api_prefix)
app.include_router(opencompute.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    async with SessionLocal() as db:
        await db.execute(text("SELECT 1"))
    result = {"status": "ready", "database": "ok"}
    if settings.app_env == "production":
        redis = Redis.from_url(settings.redis_url, socket_timeout=1, socket_connect_timeout=1)
        await redis.ping()
        await redis.aclose()
        result["redis"] = "ok"
    return result


@app.get("/health/providers")
async def health_providers() -> dict[str, str]:
    states: dict[str, str] = {}
    async with SessionLocal() as db:
        providers = list(
            (
                await db.scalars(
                    select(ResourceProvider).where(ResourceProvider.enabled.is_(True))
                )
            ).all()
        )
    for resource in providers:
        try:
            healthy = await provider_for(resource).health_check()
            states[resource.id] = "healthy" if healthy else "unhealthy"
        except Exception:
            states[resource.id] = "not_configured"
    return states


@app.get("/internal/metrics", include_in_schema=False)
async def metrics() -> Response:
    return metrics_response()
