import asyncio
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import (
    SKU,
    Instance,
    InstanceTask,
    Order,
    OutboxEvent,
    ResourceProvider,
    User,
)
from app.providers.factory import provider_for
from app.schemas import CreateInstanceRequest
from app.services.audit import add_audit
from app.services.wallet import credit_cents, debit_cents

PROGRESS_STATES = {
    "create": ("provisioning", "running"),
    "start": ("starting", "running"),
    "stop": ("stopping", "stopped"),
    "release": ("releasing", "released"),
}
EXPECTED_STATES = {"start": "stopped", "stop": "running", "release": "stopped"}


class RetryableTaskError(RuntimeError):
    """Signals the durable worker that the provider operation should be retried."""


def _validate_provider_connection(connection) -> None:
    jupyter = urlparse(connection.jupyter_url)
    if (
        jupyter.scheme != "https"
        or not jupyter.hostname
        or jupyter.username
        or jupyter.password
        or jupyter.query
        or jupyter.fragment
    ):
        raise ValueError("Provider returned an invalid Jupyter URL")
    if not re.fullmatch(r"[A-Za-z0-9.-]{1,160}", connection.ssh_host):
        raise ValueError("Provider returned an invalid SSH host")
    if not 1 <= connection.ssh_port <= 65535:
        raise ValueError("Provider returned an invalid SSH port")


def price_for_mode(sku: SKU, mode: str) -> int:
    return {
        "hourly": sku.price_hour_cents,
        "daily": sku.price_day_cents,
        "weekly": sku.price_week_cents,
        "monthly": sku.price_month_cents,
    }[mode]


def _request_hash(value: dict[str, object]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _assert_same_request(task: InstanceTask, request_hash: str) -> None:
    if task.request_hash != request_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "IDEMPOTENCY_CONFLICT",
                "message": "同一幂等键不能用于不同请求",
            },
        )


def _new_task_event(task_id: str) -> OutboxEvent:
    return OutboxEvent(
        event_type="instance.task_requested",
        aggregate_type="instance_task",
        aggregate_id=task_id,
        payload={"task_id": task_id},
    )


async def _dispatch_demo_outbox() -> None:
    if settings.demo_auto_dispatch:
        from app.services.outbox import dispatch_outbox_once

        asyncio.create_task(dispatch_outbox_once())


async def create_instance(
    db: AsyncSession,
    *,
    user: User,
    payload: CreateInstanceRequest,
    idempotency_key: str,
    request_id: str | None,
) -> tuple[Instance, InstanceTask]:
    operation = "instances.create"
    request_hash = _request_hash(payload.model_dump(mode="json"))
    locked_user = await db.get(User, user.id, with_for_update=True)
    if not locked_user or locked_user.status != "active":
        raise HTTPException(status_code=401, detail={"code": "ACCOUNT_UNAVAILABLE"})

    existing = await db.scalar(
        select(InstanceTask).where(
            InstanceTask.actor_id == user.id,
            InstanceTask.operation == operation,
            InstanceTask.idempotency_key == idempotency_key,
        )
    )
    if existing:
        _assert_same_request(existing, request_hash)
        instance = await db.get(Instance, existing.instance_id)
        if instance is None or instance.user_id != user.id:
            raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT"})
        return instance, existing

    sku = await db.get(SKU, payload.sku_id, with_for_update=True)
    if not sku or sku.status != "published":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SKU_UNAVAILABLE", "message": "商品不存在或已下架"},
        )
    if sku.inventory_available < 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "INVENTORY_CHANGED", "message": "库存刚刚发生变化，请重新选择"},
        )

    amount = price_for_mode(sku, payload.billing_mode)
    if locked_user.balance_cents < amount:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "INSUFFICIENT_BALANCE", "message": "演示余额不足"},
        )

    sku.inventory_available -= 1
    sku.inventory_reserved += 1
    order = Order(
        user_id=user.id,
        sku_id=sku.id,
        billing_mode=payload.billing_mode,
        amount_cents=amount,
        status="pending",
        idempotency_key=idempotency_key,
    )
    db.add(order)
    await db.flush()
    wallet_row = await debit_cents(
        db,
        user=locked_user,
        amount_cents=amount,
        transaction_type="debit",
        idempotency_key=f"debit:{idempotency_key}",
        description="创建实例预付",
        order_id=order.id,
    )
    if wallet_row is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"code": "INSUFFICIENT_BALANCE", "message": "演示余额不足"},
        )
    instance = Instance(
        user_id=user.id,
        sku_id=sku.id,
        order_id=order.id,
        name=payload.name,
        image=payload.image,
        billing_mode=payload.billing_mode,
        status="pending",
    )
    db.add(instance)
    await db.flush()
    task = InstanceTask(
        instance_id=instance.id,
        actor_id=user.id,
        operation=operation,
        action="create",
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        previous_instance_status="pending",
        triggered_by="user",
    )
    db.add(task)
    await db.flush()
    db.add(_new_task_event(task.id))
    add_audit(
        db,
        actor_type="user",
        actor_id=user.id,
        action="instance.create_requested",
        object_type="instance",
        object_id=instance.id,
        summary={"sku_id": sku.id, "task_id": task.id, "order_id": order.id},
        request_id=request_id,
    )
    await db.commit()
    await db.refresh(task)
    await _dispatch_demo_outbox()
    return instance, task


async def request_action(
    db: AsyncSession,
    *,
    instance_id: str,
    user: User,
    action: str,
    idempotency_key: str,
    request_id: str | None,
) -> InstanceTask:
    if action not in EXPECTED_STATES:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ACTION"})
    instance = await db.scalar(
        select(Instance)
        .where(Instance.id == instance_id, Instance.user_id == user.id)
        .with_for_update()
    )
    if not instance:
        raise HTTPException(status_code=404, detail={"code": "INSTANCE_NOT_FOUND"})

    operation = f"instances.{instance.id}.{action}"
    request_hash = _request_hash({"instance_id": instance.id, "action": action})
    existing = await db.scalar(
        select(InstanceTask).where(
            InstanceTask.actor_id == user.id,
            InstanceTask.operation == operation,
            InstanceTask.idempotency_key == idempotency_key,
        )
    )
    if existing:
        _assert_same_request(existing, request_hash)
        return existing

    expected = EXPECTED_STATES[action]
    if instance.status != expected:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INVALID_INSTANCE_STATE",
                "message": f"当前状态 {instance.status} 不允许执行 {action}",
            },
        )

    if action == "start":
        sku = await db.get(SKU, instance.sku_id, with_for_update=True)
        if not sku or sku.inventory_available < 1:
            raise HTTPException(
                status_code=409,
                detail={"code": "INVENTORY_CHANGED", "message": "当前无可用 GPU，请稍后重试"},
            )
        sku.inventory_available -= 1
        sku.inventory_reserved += 1

    previous_status = instance.status
    instance.status = PROGRESS_STATES[action][0]
    task = InstanceTask(
        instance_id=instance.id,
        actor_id=user.id,
        operation=operation,
        action=action,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        previous_instance_status=previous_status,
        triggered_by="user",
    )
    db.add(task)
    await db.flush()
    db.add(_new_task_event(task.id))
    add_audit(
        db,
        actor_type="user",
        actor_id=user.id,
        action=f"instance.{action}_requested",
        object_type="instance",
        object_id=instance.id,
        summary={"task_id": task.id},
        request_id=request_id,
    )
    await db.commit()
    await db.refresh(task)
    await _dispatch_demo_outbox()
    return task


async def _load_task_context(
    db: AsyncSession, task_id: str
) -> tuple[InstanceTask, Instance, SKU, ResourceProvider | None] | None:
    task = await db.scalar(
        select(InstanceTask).where(InstanceTask.id == task_id).with_for_update()
    )
    if not task:
        return None
    instance = await db.get(Instance, task.instance_id, with_for_update=True)
    if not instance:
        return None
    sku = await db.get(SKU, instance.sku_id, with_for_update=True)
    if not sku:
        return None
    resource = await db.get(ResourceProvider, sku.provider_id) if sku.provider_id else None
    return task, instance, sku, resource


async def _refund_failed_create(
    db: AsyncSession, task: InstanceTask, instance: Instance, sku: SKU
) -> None:
    order = await db.get(Order, instance.order_id, with_for_update=True)
    user = await db.get(User, instance.user_id, with_for_update=True)
    if not order or not user:
        return
    refund_key = f"refund:{task.id}:{task.retry_count}"
    await credit_cents(
        db,
        user=user,
        amount_cents=order.amount_cents,
        transaction_type="refund",
        idempotency_key=refund_key,
        description="实例创建失败退款",
        order_id=order.id,
    )
    order.status = "failed"
    sku.inventory_reserved = max(0, sku.inventory_reserved - 1)
    sku.inventory_available += 1


async def _record_provider_failure(task_id: str, exc: Exception) -> bool:
    async with SessionLocal() as db:
        context = await _load_task_context(db, task_id)
        if context is None:
            return False
        task, instance, sku, _ = context
        if task.status == "succeeded":
            return False
        task.attempt_count += 1
        task.error_code = "PROVIDER_OPERATION_FAILED"
        task.error_summary = f"Provider operation failed ({type(exc).__name__})"
        task.lease_expires_at = None
        if task.attempt_count < settings.task_max_attempts:
            task.status = "queued"
            task.progress = 0
            add_audit(
                db,
                actor_type="system",
                actor_id="worker",
                action=f"instance.{task.action}_retry_scheduled",
                object_type="instance_task",
                object_id=task.id,
                summary={"attempt_count": task.attempt_count},
                result="retrying",
            )
            await db.commit()
            return True

        task.status = "manual_review"
        task.completed_at = datetime.now(UTC)
        task.progress = 100
        instance.status = task.previous_instance_status or "failed"
        if task.action == "create":
            await _refund_failed_create(db, task, instance, sku)
        elif task.action == "start":
            sku.inventory_reserved = max(0, sku.inventory_reserved - 1)
            sku.inventory_available += 1
        add_audit(
            db,
            actor_type="system",
            actor_id="worker",
            action=f"instance.{task.action}_manual_review",
            object_type="instance",
            object_id=instance.id,
            summary={"task_id": task.id, "error_code": task.error_code},
            result="failed",
        )
        await db.commit()
        return False


async def process_instance_task(task_id: str) -> None:
    async with SessionLocal() as db:
        context = await _load_task_context(db, task_id)
        if context is None:
            return
        task, instance, _, resource = context
        now = datetime.now(UTC)
        if task.status in {"succeeded", "failed", "manual_review"}:
            return
        if task.status == "running" and task.lease_expires_at and task.lease_expires_at > now:
            return
        task.status = "running"
        task.progress = 20
        task.started_at = task.started_at or now
        task.lease_expires_at = now + timedelta(seconds=settings.task_lease_seconds)
        instance.status = PROGRESS_STATES[task.action][0]
        provider = provider_for(resource)
        provider_instance_id = instance.provider_instance_id or instance.id
        await db.commit()

        try:
            if task.action == "create":
                connection = await provider.create_instance(instance.id, idempotency_key=task.id)
                _validate_provider_connection(connection)
            elif task.action == "start":
                await provider.start_instance(provider_instance_id, idempotency_key=task.id)
                connection = None
            elif task.action == "stop":
                await provider.stop_instance(provider_instance_id, idempotency_key=task.id)
                connection = None
            else:
                await provider.release_instance(provider_instance_id, idempotency_key=task.id)
                connection = None
        except Exception as exc:
            if await _record_provider_failure(task_id, exc):
                raise RetryableTaskError("provider operation failed") from None
            return

    async with SessionLocal() as db:
        context = await _load_task_context(db, task_id)
        if context is None:
            return
        task, instance, sku, resource = context
        if task.status == "succeeded":
            return
        if task.action == "create" and connection is not None:
            instance.provider_instance_id = connection.provider_instance_id
            instance.ssh_host = connection.ssh_host
            instance.ssh_port = connection.ssh_port
            instance.jupyter_url = connection.jupyter_url
            instance.credential_hint = connection.credential_hint
            order = await db.get(Order, instance.order_id, with_for_update=True)
            if order:
                order.status = "fulfilled"
        task.status = "succeeded"
        task.progress = 100
        task.completed_at = datetime.now(UTC)
        task.lease_expires_at = None
        task.error_code = None
        task.error_summary = None
        instance.status = PROGRESS_STATES[task.action][1]
        if task.action in {"create", "start"}:
            sku.inventory_reserved = max(0, sku.inventory_reserved - 1)
        elif task.action == "stop":
            sku.inventory_available += 1
        elif task.action == "release":
            instance.released_at = datetime.now(UTC)
        add_audit(
            db,
            actor_type="system",
            actor_id=resource.id if resource else "provider",
            action=f"instance.{task.action}_succeeded",
            object_type="instance",
            object_id=instance.id,
            summary={"task_id": task.id},
        )
        await db.commit()


async def retry_failed_task(
    db: AsyncSession, *, task_id: str, admin_id: str, request_id: str | None
) -> InstanceTask:
    context = await _load_task_context(db, task_id)
    if context is None:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND"})
    task, instance, sku, _ = context
    if task.status not in {"failed", "manual_review"}:
        raise HTTPException(status_code=409, detail={"code": "TASK_NOT_RETRYABLE"})

    if task.action == "create":
        order = await db.get(Order, instance.order_id, with_for_update=True)
        user = await db.get(User, instance.user_id, with_for_update=True)
        if not order or not user or user.balance_cents < order.amount_cents:
            raise HTTPException(status_code=409, detail={"code": "RETRY_BALANCE_UNAVAILABLE"})
        if sku.inventory_available < 1:
            raise HTTPException(status_code=409, detail={"code": "INVENTORY_CHANGED"})
        wallet_row = await debit_cents(
            db,
            user=user,
            amount_cents=order.amount_cents,
            transaction_type="debit",
            idempotency_key=f"retry-debit:{task.id}:{task.retry_count + 1}",
            description="管理员重试实例创建预付",
            order_id=order.id,
        )
        if wallet_row is None:
            raise HTTPException(status_code=409, detail={"code": "RETRY_BALANCE_UNAVAILABLE"})
        sku.inventory_available -= 1
        sku.inventory_reserved += 1
        order.status = "pending"
    elif task.action == "start":
        if sku.inventory_available < 1:
            raise HTTPException(status_code=409, detail={"code": "INVENTORY_CHANGED"})
        sku.inventory_available -= 1
        sku.inventory_reserved += 1

    task.status = "queued"
    task.progress = 0
    task.retry_count += 1
    task.attempt_count = 0
    task.error_code = None
    task.error_summary = None
    task.completed_at = None
    task.started_at = None
    task.lease_expires_at = None
    instance.status = PROGRESS_STATES[task.action][0]
    db.add(_new_task_event(task.id))
    add_audit(
        db,
        actor_type="admin",
        actor_id=admin_id,
        action="task.retry_requested",
        object_type="instance_task",
        object_id=task.id,
        summary={"retry_count": task.retry_count},
        request_id=request_id,
    )
    await db.commit()
    await db.refresh(task)
    await _dispatch_demo_outbox()
    return task


async def recover_stuck_tasks() -> list[str]:
    now = datetime.now(UTC)
    recovered: list[str] = []
    async with SessionLocal() as db:
        tasks = list(
            (
                await db.scalars(
                    select(InstanceTask)
                    .where(
                        InstanceTask.status == "running",
                        or_(
                            InstanceTask.lease_expires_at.is_(None),
                            InstanceTask.lease_expires_at <= now,
                        ),
                    )
                    .with_for_update(skip_locked=True)
                    .limit(100)
                )
            ).all()
        )
        for task in tasks:
            task.status = "queued"
            task.progress = 0
            task.lease_expires_at = None
            db.add(_new_task_event(task.id))
            recovered.append(task.id)
        await db.commit()
    return recovered
