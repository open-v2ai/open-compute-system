import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.dependencies.auth import current_user
from app.models import Instance, InstanceTask, Order, User, WalletTransaction
from app.schemas import (
    CreateInstanceRequest,
    CreateInstanceResponse,
    InstanceResponse,
    OrderResponse,
    TaskResponse,
    WalletTransactionResponse,
)
from app.services.instances import create_instance, request_action

router = APIRouter(tags=["instances"])


def get_idempotency_key(value: str | None, action: str) -> str:
    return value or f"{action}:{uuid.uuid4()}"


@router.post(
    "/instances", response_model=CreateInstanceResponse, status_code=status.HTTP_202_ACCEPTED
)
async def create(
    payload: CreateInstanceRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateInstanceResponse:
    instance, task = await create_instance(
        db,
        user=user,
        payload=payload,
        idempotency_key=get_idempotency_key(idempotency_key, "create"),
        request_id=request.state.request_id,
    )
    return CreateInstanceResponse(instance_id=instance.id, task_id=task.id, status=task.status)


@router.get("/instances", response_model=list[InstanceResponse])
async def list_instances(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> list[Instance]:
    query = (
        select(Instance)
        .where(Instance.user_id == user.id)
        .options(selectinload(Instance.sku))
        .order_by(Instance.created_at.desc())
    )
    return list((await db.scalars(query)).all())


@router.get("/instances/{instance_id}", response_model=InstanceResponse)
async def get_instance(
    instance_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> Instance:
    instance = await db.scalar(
        select(Instance)
        .where(Instance.id == instance_id, Instance.user_id == user.id)
        .options(selectinload(Instance.sku))
    )
    if not instance:
        raise HTTPException(status_code=404, detail={"code": "INSTANCE_NOT_FOUND"})
    return instance


@router.post("/instances/{instance_id}/{action}", response_model=TaskResponse, status_code=202)
async def action(
    instance_id: str,
    action: str,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> InstanceTask:
    return await request_action(
        db,
        instance_id=instance_id,
        user=user,
        action=action,
        idempotency_key=get_idempotency_key(idempotency_key, action),
        request_id=request.state.request_id,
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def task(
    task_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> InstanceTask:
    result = await db.scalar(
        select(InstanceTask)
        .join(Instance, Instance.id == InstanceTask.instance_id)
        .where(InstanceTask.id == task_id, Instance.user_id == user.id)
    )
    if not result:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND"})
    return result


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> list[Order]:
    query = (
        select(Order)
        .where(Order.user_id == user.id)
        .options(selectinload(Order.sku))
        .order_by(Order.created_at.desc())
    )
    return list((await db.scalars(query)).all())


@router.get("/wallet/transactions", response_model=list[WalletTransactionResponse])
async def wallet_transactions(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
) -> list[WalletTransaction]:
    query = (
        select(WalletTransaction)
        .where(WalletTransaction.user_id == user.id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(200)
    )
    return list((await db.scalars(query)).all())
