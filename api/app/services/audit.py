from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def add_audit(
    db: AsyncSession,
    *,
    actor_type: str,
    actor_id: str,
    action: str,
    object_type: str,
    object_id: str,
    summary: dict | None = None,
    request_id: str | None = None,
    result: str = "succeeded",
) -> None:
    db.add(
        AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            summary=summary,
            request_id=request_id,
            result=result,
        )
    )

