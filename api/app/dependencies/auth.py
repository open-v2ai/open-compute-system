from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_session
from app.db.session import get_db
from app.models import AdminUser, User


def unauthorized(code: str = "AUTH_REQUIRED") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": "请先登录"},
    )


async def current_user(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_session(session_token or "")
    if not payload or payload.get("type") != "user":
        raise unauthorized()
    user = await db.get(User, payload["sub"])
    if not user or user.status != "active":
        raise unauthorized("ACCOUNT_UNAVAILABLE")
    return user


async def current_admin(
    session_token: str | None = Cookie(default=None, alias=settings.session_cookie),
    db: AsyncSession = Depends(get_db),
) -> AdminUser:
    if not settings.admin_login_enabled:
        raise HTTPException(status_code=404, detail={"code": "ADMIN_LOGIN_DISABLED"})
    payload = decode_session(session_token or "")
    if not payload or payload.get("type") != "admin":
        raise unauthorized("ADMIN_AUTH_REQUIRED")
    admin = await db.get(AdminUser, payload["sub"])
    if not admin or admin.status != "active":
        raise unauthorized("ADMIN_ACCOUNT_UNAVAILABLE")
    return admin

