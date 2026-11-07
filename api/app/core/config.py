import re
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_SESSION_SECRET = "open-compute-system-local-development-secret"


class Settings(BaseSettings):
    app_name: str = "Open Compute System API"
    app_env: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./open_compute_system.db"
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_key_prefix: str = ""
    celery_queue: str = "celery"
    session_secret: str = LOCAL_SESSION_SECRET
    session_cookie: str = "ocs_session"
    csrf_cookie: str = "ocs_csrf"
    cookie_path: str = "/"
    public_demo_enabled: bool = False
    session_cookie_secure: bool | None = None
    web_origin: str = "http://127.0.0.1:3000"
    admin_origin: str = "http://127.0.0.1:3000"
    trusted_hosts: str = "localhost,127.0.0.1,testserver"
    mock_provider_delay_seconds: float = 0.35
    demo_auto_dispatch: bool = True
    demo_seed_enabled: bool = True
    self_registration_enabled: bool = True
    admin_login_enabled: bool = True
    admin_mfa_totp_secret: SecretStr | None = None
    allow_mock_provider_in_production: bool = False
    allow_mock_inference_in_production: bool = False
    task_lease_seconds: int = 300
    task_max_attempts: int = 3
    outbox_lease_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cookie_path")
    @classmethod
    def validate_cookie_path(cls, value: str) -> str:
        if not re.fullmatch(r"/(?:[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*)?", value):
            raise ValueError("COOKIE_PATH must be an absolute application path")
        return value

    @field_validator("session_secret")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("SESSION_SECRET must contain at least 32 characters")
        return value

    @field_validator("redis_key_prefix", "celery_queue")
    @classmethod
    def validate_task_namespace(cls, value: str, info) -> str:
        if info.field_name == "redis_key_prefix" and value == "":
            return value
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", value):
            raise ValueError("Task namespaces must be 1-64 letters, digits, underscores or hyphens")
        return value

    @field_validator("web_origin", "admin_origin")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("Origin contains an invalid port") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Origin must be an HTTP(S) origin without path or credentials")
        return normalized

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.public_demo_enabled and (
            self.app_env == "production"
            or self.admin_login_enabled
            or self.self_registration_enabled
            or not self.demo_seed_enabled
            or self.session_secret == LOCAL_SESSION_SECRET
            or not self.secure_cookies
            or any(not origin.startswith("https://") for origin in self.allowed_origins)
        ):
            raise ValueError(
                "Public demo requires HTTPS, an explicit secret, demo seeding, "
                "and disabled admin login/self-registration in a non-production environment"
            )
        if self.app_env == "production" and self.session_secret == LOCAL_SESSION_SECRET:
            raise ValueError("SESSION_SECRET must be explicitly configured in production")
        if self.app_env == "production" and self.demo_seed_enabled:
            raise ValueError("DEMO_SEED_ENABLED must be false in production")
        if self.app_env == "production" and self.self_registration_enabled:
            raise ValueError(
                "SELF_REGISTRATION_ENABLED must remain false until phone and email verification "
                "are integrated"
            )
        if (
            self.app_env == "production"
            and self.admin_login_enabled
            and (
                self.admin_mfa_totp_secret is None
                or len(self.admin_mfa_totp_secret.get_secret_value().strip()) < 16
            )
        ):
            raise ValueError(
                "ADMIN_MFA_TOTP_SECRET is required when production admin login is enabled"
            )
        if self.app_env == "production" and any(
            not origin.startswith("https://") for origin in self.allowed_origins
        ):
            raise ValueError("WEB_ORIGIN and ADMIN_ORIGIN must use HTTPS in production")
        if self.app_env == "production" and (
            not self.allowed_hosts
            or "*" in self.allowed_hosts
            or "testserver" in self.allowed_hosts
        ):
            raise ValueError("TRUSTED_HOSTS must be explicitly configured in production")
        if self.app_env == "production" and self.session_cookie_secure is False:
            raise ValueError("SESSION_COOKIE_SECURE cannot be false in production")
        return self

    @property
    def secure_cookies(self) -> bool:
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.app_env == "production"

    @property
    def allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]

    @property
    def allowed_origins(self) -> list[str]:
        return list(dict.fromkeys([self.web_origin.rstrip("/"), self.admin_origin.rstrip("/")]))

    @property
    def docs_enabled(self) -> bool:
        return self.app_env != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
