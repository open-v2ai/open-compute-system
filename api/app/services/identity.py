from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import verify_password
from app.models import User


class IdentityError(Exception):
    code = "IDENTITY_ERROR"


class IdentityAlreadyBound(IdentityError):
    code = "IDENTITY_ALREADY_BOUND"


class IdentityTypeAlreadyBound(IdentityError):
    code = "IDENTITY_TYPE_ALREADY_BOUND"


class IdentityNotBound(IdentityError):
    code = "IDENTITY_NOT_BOUND"


class LastIdentity(IdentityError):
    code = "LAST_IDENTITY_REQUIRED"


class InvalidPassword(IdentityError):
    code = "INVALID_PASSWORD"


class DemoIdentityReadOnly(IdentityError):
    code = "DEMO_IDENTITY_READ_ONLY"


async def user_for_identity(
    db: AsyncSession, *, phone: str | None = None, email: str | None = None
) -> User | None:
    if phone is not None:
        return await db.scalar(select(User).where(User.phone == phone))
    if email is not None:
        return await db.scalar(select(User).where(User.email == email))
    return None


async def identity_is_bound(
    db: AsyncSession,
    *,
    phone: str | None = None,
    email: str | None = None,
    excluding_user_id: str | None = None,
) -> bool:
    filters = []
    if phone is not None:
        filters.append(User.phone == phone)
    if email is not None:
        filters.append(User.email == email)
    if not filters:
        return False
    statement = select(User.id).where(or_(*filters))
    if excluding_user_id is not None:
        statement = statement.where(User.id != excluding_user_id)
    return await db.scalar(statement) is not None


async def bind_identity(
    db: AsyncSession,
    *,
    user: User,
    current_password: str,
    phone: str | None = None,
    email: str | None = None,
) -> str:
    if settings.public_demo_enabled:
        raise DemoIdentityReadOnly
    if not verify_password(current_password, user.password_hash):
        raise InvalidPassword
    identity_type = "phone" if phone is not None else "email"
    if getattr(user, identity_type) is not None:
        raise IdentityTypeAlreadyBound
    if await identity_is_bound(
        db, phone=phone, email=email, excluding_user_id=user.id
    ):
        raise IdentityAlreadyBound

    setattr(user, identity_type, phone if phone is not None else email)
    try:
        await db.flush()
    except IntegrityError as error:
        await db.rollback()
        raise IdentityAlreadyBound from error
    return identity_type


async def unbind_identity(
    db: AsyncSession, *, user: User, identity_type: str, current_password: str
) -> None:
    if settings.public_demo_enabled:
        raise DemoIdentityReadOnly
    if not verify_password(current_password, user.password_hash):
        raise InvalidPassword
    if identity_type not in {"phone", "email"} or getattr(user, identity_type) is None:
        raise IdentityNotBound
    remaining_type = "email" if identity_type == "phone" else "phone"
    if getattr(user, remaining_type) is None:
        raise LastIdentity
    setattr(user, identity_type, None)
    await db.flush()
