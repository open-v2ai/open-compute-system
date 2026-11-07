from collections.abc import Iterable

from fastapi import Depends, HTTPException, status

from app.dependencies.auth import current_admin
from app.models import AdminUser

ALL_PERMISSIONS = {
    "dashboard.read",
    "providers.read",
    "catalog.read",
    "catalog.cost.read",
    "catalog.manage",
    "instances.read",
    "tasks.read",
    "tasks.manage",
    "users.read",
    "users.balance.read",
    "orders.read",
    "audit.read",
    "inference.read",
    "inference.manage",
    "inference.cost.read",
}

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "super_admin": ALL_PERMISSIONS,
    "operations": {
        "dashboard.read",
        "providers.read",
        "catalog.read",
        "catalog.manage",
        "instances.read",
        "tasks.read",
        "users.read",
        "orders.read",
        "inference.read",
        "inference.manage",
    },
    "resource_ops": {
        "dashboard.read",
        "providers.read",
        "catalog.read",
        "instances.read",
        "tasks.read",
        "tasks.manage",
        "inference.read",
    },
    "finance": {
        "dashboard.read",
        "providers.read",
        "catalog.read",
        "catalog.cost.read",
        "users.read",
        "users.balance.read",
        "orders.read",
        "inference.read",
        "inference.cost.read",
    },
    "sales": {"dashboard.read"},
    "support": {
        "dashboard.read",
        "catalog.read",
        "instances.read",
        "tasks.read",
        "users.read",
        "orders.read",
        "inference.read",
    },
    "risk": {"dashboard.read", "instances.read", "tasks.read", "users.read"},
    "content": set(),
    "auditor": {
        "dashboard.read",
        "providers.read",
        "catalog.read",
        "catalog.cost.read",
        "instances.read",
        "tasks.read",
        "users.read",
        "users.balance.read",
        "orders.read",
        "audit.read",
        "inference.read",
        "inference.cost.read",
    },
}


def permissions_for(admin: AdminUser) -> set[str]:
    return set(ROLE_PERMISSIONS.get(admin.role, set()))


def has_permissions(admin: AdminUser, required: Iterable[str]) -> bool:
    return set(required).issubset(permissions_for(admin))


def require_permissions(*required: str):
    async def dependency(admin: AdminUser = Depends(current_admin)) -> AdminUser:
        if not has_permissions(admin, required):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ADMIN_PERMISSION_DENIED", "message": "当前角色无权执行此操作"},
            )
        return admin

    return dependency
