import asyncio
from collections.abc import Awaitable

from celery import Celery

from app.core.config import settings
from app.db.session import engine
from app.services.instances import RetryableTaskError, process_instance_task, recover_stuck_tasks

celery_app = Celery("open-compute-system", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue=settings.celery_queue,
    task_default_exchange=settings.celery_queue,
    task_default_routing_key=settings.celery_queue,
    broker_transport_options={
        "global_keyprefix": f"{settings.redis_key_prefix}:broker:",
    } if settings.redis_key_prefix else {},
    result_backend_transport_options={
        "global_keyprefix": f"{settings.redis_key_prefix}:result:",
    } if settings.redis_key_prefix else {},
    result_expires=3600,
    task_track_started=True,
    beat_schedule={
        "dispatch-outbox-every-two-seconds": {
            "task": "outbox.dispatch",
            "schedule": 2.0,
        },
        "recover-stuck-instance-tasks-every-minute": {
            "task": "instances.recover_stuck",
            "schedule": 60.0,
        },
    },
)


def run_async_service[T](operation: Awaitable[T]) -> T:
    async def run() -> T:
        try:
            return await operation
        finally:
            # Celery creates a new loop per task. asyncpg pooled connections belong
            # to their original loop, so close them before asyncio.run closes it.
            await engine.dispose()

    return asyncio.run(run())


@celery_app.task(
    name="instances.process",
    autoretry_for=(RetryableTaskError,),
    retry_backoff=True,
    max_retries=3,
)
def process_instance_task_job(task_id: str) -> None:
    run_async_service(process_instance_task(task_id))


@celery_app.task(name="outbox.dispatch")
def dispatch_outbox_job() -> int:
    from app.services.outbox import dispatch_outbox_once

    return run_async_service(dispatch_outbox_once(use_celery=True))


@celery_app.task(name="instances.recover_stuck")
def recover_stuck_tasks_job() -> int:
    return len(run_async_service(recover_stuck_tasks()))
