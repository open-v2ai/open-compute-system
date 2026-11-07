from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import OutboxEvent
from app.services.instances import process_instance_task


async def dispatch_outbox_once(*, use_celery: bool = False, limit: int = 50) -> int:
    async with SessionLocal() as db:
        events = list(
            (
                await db.scalars(
                    select(OutboxEvent)
                    .where(
                        or_(
                            and_(
                                OutboxEvent.status.in_(["pending", "retry_wait"]),
                                OutboxEvent.available_at <= datetime.now(UTC),
                            ),
                            and_(
                                OutboxEvent.status == "publishing",
                                or_(
                                    OutboxEvent.lease_expires_at.is_(None),
                                    OutboxEvent.lease_expires_at <= datetime.now(UTC),
                                ),
                            ),
                        )
                    )
                    .order_by(OutboxEvent.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            ).all()
        )
        for event in events:
            event.status = "publishing"
            event.attempts += 1
            event.lease_expires_at = datetime.now(UTC) + timedelta(
                seconds=settings.outbox_lease_seconds
            )
        await db.commit()

        delivered = 0
        for event in events:
            try:
                if event.event_type != "instance.task_requested":
                    raise ValueError(f"Unsupported outbox event: {event.event_type}")
                task_id = str(event.payload["task_id"])
                if use_celery:
                    from app.workers.celery_app import process_instance_task_job

                    process_instance_task_job.delay(task_id)
                else:
                    await process_instance_task(task_id)
                event.status = "published"
                event.published_at = datetime.now(UTC)
                event.last_error = None
                event.lease_expires_at = None
                delivered += 1
            except Exception as exc:
                event.status = "retry_wait" if event.attempts < 5 else "failed"
                event.last_error = str(exc)[:240]
                event.lease_expires_at = None
                event.available_at = datetime.now(UTC) + timedelta(
                    seconds=min(60, 2 ** event.attempts)
                )
        await db.commit()
        return delivered
