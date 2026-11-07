import secrets
from typing import Literal

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.identity import mask_email
from app.core.permissions import permissions_for
from app.core.security import create_session, hash_password, mask_phone, verify_password
from app.db.session import get_db
from app.dependencies.auth import current_admin, current_user
from app.dependencies.rate_limit import rate_limit
from app.models import AdminUser, User
from app.schemas import (
    AdminLoginRequest,
    AdminResponse,
    BindIdentityRequest,
    LoginRequest,
    RegisterRequest,
    UnbindIdentityRequest,
    UserResponse,
)
from app.services.audit import add_audit
from app.services.identity import (
    DemoIdentityReadOnly,
    IdentityAlreadyBound,
    IdentityNotBound,
    IdentityTypeAlreadyBound,
    InvalidPassword,
    LastIdentity,
    bind_identity,
    identity_is_bound,
    unbind_identity,
    user_for_identity,
)

router = APIRouter(tags=["auth"])


def masked_identity(*, phone: str | None = None, email: str | None = None) -> str:
    if phone is not None:
        return mask_phone(phone)
    if email is not None:
        return mask_email(email)
    return "***"


def identity_error(error: Exception) -> HTTPException:
    if isinstance(error, DemoIdentityReadOnly):
        return HTTPException(
            status_code=403,
            detail={"code": error.code, "message": "公开演示站不允许修改登录方式"},
        )
    if isinstance(error, InvalidPassword):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": error.code, "message": "当前密码错误"},
        )
    if isinstance(error, IdentityAlreadyBound):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": error.code, "message": "该手机号或邮箱已被其他账号绑定"},
        )
    if isinstance(error, IdentityTypeAlreadyBound):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": error.code, "message": "该类型的登录方式已绑定，请先解绑"},
        )
    if isinstance(error, IdentityNotBound):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": error.code, "message": "该登录方式尚未绑定"},
        )
    if isinstance(error, LastIdentity):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": error.code, "message": "至少保留一种登录方式"},
        )
    return HTTPException(status_code=500, detail={"code": "IDENTITY_UPDATE_FAILED"})


def set_session_cookie(response: Response, actor_id: str, actor_type: str) -> None:
    csrf_token = secrets.token_urlsafe(32)
    ttl_hours = 4 if actor_type == "admin" else 12
    response.set_cookie(
        key=settings.session_cookie,
        value=create_session(actor_id, actor_type, csrf_token, ttl_hours=ttl_hours),
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=ttl_hours * 60 * 60,
        path=settings.cookie_path,
    )
    response.set_cookie(
        key=settings.csrf_cookie,
        value=csrf_token,
        httponly=False,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=ttl_hours * 60 * 60,
        path=settings.cookie_path,
    )


@router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=201,
    dependencies=[Depends(rate_limit("register", requests=5, window_seconds=3600))],
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    if not settings.self_registration_enabled:
        raise HTTPException(status_code=404, detail={"code": "SELF_REGISTRATION_DISABLED"})
    if not payload.accepted_terms:
        raise HTTPException(
            status_code=422,
            detail={"code": "TERMS_REQUIRED", "message": "请先同意服务协议和隐私政策"},
        )
    if await identity_is_bound(db, phone=payload.phone, email=payload.email):
        label = "手机号" if payload.phone is not None else "邮箱"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ACCOUNT_EXISTS", "message": f"该{label}已注册"},
        )
    user = User(
        phone=payload.phone,
        email=payload.email,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname.strip() or "算力用户",
        balance_cents=100_000,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as error:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ACCOUNT_EXISTS", "message": "该手机号或邮箱已注册"},
        ) from error
    add_audit(
        db,
        actor_type="user",
        actor_id=user.id,
        action="auth.register",
        object_type="user",
        object_id=user.id,
        summary={
            "identity_type": "phone" if payload.phone is not None else "email",
            "identity": masked_identity(phone=payload.phone, email=payload.email),
        },
        request_id=request.state.request_id,
    )
    await db.commit()
    await db.refresh(user)
    set_session_cookie(response, user.id, "user")
    return user


@router.post(
    "/auth/login",
    response_model=UserResponse,
    dependencies=[Depends(rate_limit("user_login", requests=10, window_seconds=300))],
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await user_for_identity(db, phone=payload.phone, email=payload.email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "手机号、邮箱或密码错误"},
        )
    if user.status != "active":
        raise HTTPException(status_code=403, detail={"code": "ACCOUNT_UNAVAILABLE"})
    add_audit(
        db,
        actor_type="user",
        actor_id=user.id,
        action="auth.login",
        object_type="user",
        object_id=user.id,
        summary={
            "identity_type": "phone" if payload.phone is not None else "email",
            "identity": masked_identity(phone=payload.phone, email=payload.email),
        },
        request_id=request.state.request_id,
    )
    await db.commit()
    set_session_cookie(response, user.id, "user")
    return user


@router.post(
    "/admin/auth/login",
    response_model=AdminResponse,
    dependencies=[Depends(rate_limit("admin_login", requests=5, window_seconds=300))],
)
async def admin_login(
    payload: AdminLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AdminResponse:
    if not settings.admin_login_enabled:
        raise HTTPException(status_code=404, detail={"code": "ADMIN_LOGIN_DISABLED"})
    admin = await db.scalar(select(AdminUser).where(AdminUser.username == payload.username))
    if settings.app_env == "production":
        secret = settings.admin_mfa_totp_secret
        valid_mfa = bool(
            secret
            and pyotp.TOTP(secret.get_secret_value()).verify(payload.mfa_code, valid_window=1)
        )
    else:
        valid_mfa = payload.mfa_code == "123456"
    if (
        not admin
        or admin.status != "active"
        or not verify_password(payload.password, admin.password_hash)
        or not valid_mfa
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_ADMIN_CREDENTIALS", "message": "账号、密码或 MFA 错误"},
        )
    add_audit(
        db,
        actor_type="admin",
        actor_id=admin.id,
        action="admin.login",
        object_type="admin_user",
        object_id=admin.id,
        summary={"mfa": True},
        request_id=request.state.request_id,
    )
    await db.commit()
    set_session_cookie(response, admin.id, "admin")
    return AdminResponse(
        id=admin.id,
        username=admin.username,
        display_name=admin.display_name,
        role=admin.role,
        mfa_enabled=admin.mfa_enabled,
        permissions=sorted(permissions_for(admin)),
    )


@router.get("/auth/me", response_model=UserResponse)
async def me(user: User = Depends(current_user)) -> User:
    return user


@router.post("/auth/identities", response_model=UserResponse)
async def add_identity(
    payload: BindIdentityRequest,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        identity_type = await bind_identity(
            db,
            user=user,
            current_password=payload.current_password,
            phone=payload.phone,
            email=payload.email,
        )
    except (
        DemoIdentityReadOnly, IdentityAlreadyBound, IdentityTypeAlreadyBound, InvalidPassword,
    ) as error:
        raise identity_error(error) from error
    add_audit(
        db,
        actor_type="user",
        actor_id=user.id,
        action="auth.identity_bound",
        object_type="user",
        object_id=user.id,
        summary={
            "identity_type": identity_type,
            "identity": masked_identity(phone=payload.phone, email=payload.email),
        },
        request_id=request.state.request_id,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/auth/identities/{identity_type}", response_model=UserResponse)
async def remove_identity(
    identity_type: Literal["phone", "email"],
    payload: UnbindIdentityRequest,
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    identity = getattr(user, identity_type)
    try:
        await unbind_identity(
            db,
            user=user,
            identity_type=identity_type,
            current_password=payload.current_password,
        )
    except (DemoIdentityReadOnly, IdentityNotBound, InvalidPassword, LastIdentity) as error:
        raise identity_error(error) from error
    add_audit(
        db,
        actor_type="user",
        actor_id=user.id,
        action="auth.identity_unbound",
        object_type="user",
        object_id=user.id,
        summary={
            "identity_type": identity_type,
            "identity": masked_identity(
                phone=identity if identity_type == "phone" else None,
                email=identity if identity_type == "email" else None,
            ),
        },
        request_id=request.state.request_id,
    )
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/admin/auth/me", response_model=AdminResponse)
async def admin_me(admin: AdminUser = Depends(current_admin)) -> AdminResponse:
    return AdminResponse(
        id=admin.id,
        username=admin.username,
        display_name=admin.display_name,
        role=admin.role,
        mfa_enabled=admin.mfa_enabled,
        permissions=sorted(permissions_for(admin)),
    )


@router.post("/auth/logout", status_code=204)
async def logout(response: Response) -> None:
    response.delete_cookie(settings.session_cookie, path=settings.cookie_path)
    response.delete_cookie(settings.csrf_cookie, path=settings.cookie_path)
