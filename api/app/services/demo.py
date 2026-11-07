"""Public demo admission checks; no real provider or inference backend is admitted."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InferenceModel, ResourceProvider


async def require_mock_resources(db: AsyncSession) -> None:
    real_providers = await db.scalar(
        select(func.count(ResourceProvider.id)).where(ResourceProvider.access_mode != "mock")
    )
    real_models = await db.scalar(
        select(func.count(InferenceModel.id)).where(
            InferenceModel.backend_type.not_in(["mock", "auto_router"])
        )
    )
    if real_providers or real_models:
        raise RuntimeError("Public demo refuses non-Mock resource providers or inference backends")
