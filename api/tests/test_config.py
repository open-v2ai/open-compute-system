import pytest
from pydantic import ValidationError

from app.core.config import LOCAL_SESSION_SECRET, Settings


def test_production_rejects_local_security_defaults() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", session_secret=LOCAL_SESSION_SECRET)


def test_rejects_unknown_environment_name() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="prodution")


@pytest.mark.parametrize(
    "origin",
    [
        "https://compute.example.com/path",
        "https://user:password@compute.example.com",
        "https://compute.example.com?tenant=one",
        "https://compute.example.com:invalid",
    ],
)
def test_rejects_invalid_browser_origins(origin: str) -> None:
    with pytest.raises(ValidationError):
        Settings(web_origin=origin)


def test_normalizes_trailing_origin_slash() -> None:
    configured = Settings(web_origin="http://127.0.0.1:3000/")
    assert configured.web_origin == "http://127.0.0.1:3000"


def test_production_rejects_insecure_cookie_override() -> None:
    with pytest.raises(ValidationError, match="SESSION_COOKIE_SECURE"):
        Settings(
            app_env="production",
            session_secret="s" * 40,
            session_cookie_secure=False,
            demo_seed_enabled=False,
            self_registration_enabled=False,
            web_origin="https://compute.example.com",
            admin_origin="https://ops.compute.example.com",
            trusted_hosts="compute.example.com,ops.compute.example.com",
            admin_mfa_totp_secret="JBSWY3DPEHPK3PXP",
        )


def test_production_rejects_empty_trusted_hosts() -> None:
    with pytest.raises(ValidationError, match="TRUSTED_HOSTS"):
        Settings(
            app_env="production",
            session_secret="s" * 40,
            demo_seed_enabled=False,
            self_registration_enabled=False,
            web_origin="https://compute.example.com",
            admin_origin="https://ops.compute.example.com",
            trusted_hosts="",
            admin_mfa_totp_secret="JBSWY3DPEHPK3PXP",
        )


def test_production_accepts_explicit_secure_settings() -> None:
    settings = Settings(
        app_env="production",
        session_secret="s" * 40,
        demo_seed_enabled=False,
        self_registration_enabled=False,
        web_origin="https://compute.example.com",
        admin_origin="https://ops.compute.example.com",
        trusted_hosts="compute.example.com,ops.compute.example.com",
        admin_mfa_totp_secret="JBSWY3DPEHPK3PXP",
    )
    assert settings.secure_cookies is True
    assert settings.docs_enabled is False


@pytest.mark.parametrize("field", ["redis_key_prefix", "celery_queue"])
@pytest.mark.parametrize("value", ["*", "tenant:other", "name with space", "x" * 65])
def test_rejects_unsafe_shared_task_namespaces(field: str, value: str) -> None:
    with pytest.raises(ValidationError, match="Task namespaces"):
        Settings(**{field: value})


def test_default_task_namespace_preserves_existing_bundled_queues() -> None:
    settings = Settings(_env_file=None)
    assert settings.redis_key_prefix == ""
    assert settings.celery_queue == "celery"


def test_accepts_project_scoped_task_namespaces() -> None:
    settings = Settings(redis_key_prefix="project_one", celery_queue="project_one")
    assert settings.redis_key_prefix == "project_one"
    assert settings.celery_queue == "project_one"


@pytest.mark.parametrize("value", ["", "//app", "/app/", "/app;secure", "/app?x=1"])
def test_rejects_invalid_cookie_paths(value: str) -> None:
    with pytest.raises(ValidationError, match="COOKIE_PATH"):
        Settings(cookie_path=value)


def public_demo_settings(**overrides) -> Settings:
    values = {
        "public_demo_enabled": True,
        "session_secret": "s" * 40,
        "session_cookie_secure": True,
        "admin_login_enabled": False,
        "self_registration_enabled": False,
        "web_origin": "https://demo.example.com",
        "admin_origin": "https://demo.example.com",
        "trusted_hosts": "demo.example.com",
        "cookie_path": "/open-compute-system",
    }
    values.update(overrides)
    return Settings(**values)


def test_public_demo_accepts_explicit_https_mock_configuration() -> None:
    configured = public_demo_settings()
    assert configured.cookie_path == "/open-compute-system"
    assert configured.secure_cookies


@pytest.mark.parametrize("override", [
    {"admin_login_enabled": True},
    {"self_registration_enabled": True},
    {"session_cookie_secure": False},
    {"demo_seed_enabled": False},
    {"session_secret": LOCAL_SESSION_SECRET},
    {"web_origin": "http://demo.example.com"},
    {"app_env": "production"},
])
def test_public_demo_rejects_unsafe_configuration(override) -> None:
    with pytest.raises(ValidationError, match="Public demo requires"):
        public_demo_settings(**override)
