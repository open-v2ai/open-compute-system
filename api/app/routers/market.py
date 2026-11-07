from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import SKU
from app.schemas import SKUResponse

router = APIRouter(tags=["market"])


@router.get("/market/skus", response_model=list[SKUResponse])
async def list_skus(
    region: str | None = None,
    gpu_model: str | None = None,
    in_stock: bool = False,
    sort: str = Query(default="recommended", pattern="^(recommended|price_asc|price_desc)$"),
    db: AsyncSession = Depends(get_db),
) -> list[SKU]:
    query = select(SKU).where(SKU.status == "published")
    if region:
        query = query.where(SKU.region == region)
    if gpu_model:
        query = query.where(SKU.gpu_model == gpu_model)
    if in_stock:
        query = query.where(SKU.inventory_available > 0)
    if sort == "price_asc":
        query = query.order_by(SKU.price_hour_cents.asc())
    elif sort == "price_desc":
        query = query.order_by(SKU.price_hour_cents.desc())
    else:
        query = query.order_by(SKU.recommended.desc(), SKU.price_hour_cents.asc())
    return list((await db.scalars(query)).all())
