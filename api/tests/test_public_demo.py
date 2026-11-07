import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.db.base import Base
from app.models import InferenceModel, ResourceProvider
from app.services.demo import require_mock_resources


def test_public_demo_blocks_login_identity_changes(client, monkeypatch) -> None:
    logged_in = client.post("/api/v1/auth/login", json={
        "phone": "13800138000", "password": "Demo12345",
    })
    assert logged_in.status_code == 200
    original = logged_in.json()
    monkeypatch.setattr(settings, "public_demo_enabled", True)
    headers = {"X-CSRF-Token": client.cookies.get(settings.csrf_cookie)}
    response = client.post("/api/v1/auth/identities", headers=headers, json={
        "email": "visitor@example.invalid", "current_password": "Demo12345",
    })
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "DEMO_IDENTITY_READ_ONLY"
    response = client.request("DELETE", "/api/v1/auth/identities/email", headers=headers,
                              json={"current_password": "Demo12345"})
    assert response.status_code == 403
    current = client.get("/api/v1/auth/me").json()
    assert (current["phone"], current["email"]) == (original["phone"], original["email"])


def test_disabled_admin_rejects_previously_issued_sessions(client, monkeypatch) -> None:
    response = client.post("/api/v1/admin/auth/login", json={
        "username": "admin", "password": "Admin12345", "mfa_code": "123456",
    })
    assert response.status_code == 200
    assert client.get("/api/v1/admin/auth/me").status_code == 200
    monkeypatch.setattr(settings, "admin_login_enabled", False)
    assert client.get("/api/v1/admin/auth/me").status_code == 404
    assert client.get("/api/v1/admin/users").status_code == 404


def test_session_cookie_path_is_used_for_login_and_logout(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "cookie_path", "/open-compute-system")
    response = client.post("/api/v1/auth/login", json={
        "phone": "13800138000", "password": "Demo12345",
    })
    assert response.status_code == 200
    assert all("Path=/open-compute-system" in value
               for value in response.headers.get_list("set-cookie"))
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert all("Path=/open-compute-system" in value
               for value in response.headers.get_list("set-cookie"))


@pytest.mark.parametrize("kind", ["provider", "model"])
async def test_public_demo_admission_refuses_real_backends(kind: str) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with AsyncSession(engine) as db:
            await require_mock_resources(db)
            if kind == "provider":
                db.add(ResourceProvider(name="Real", provider_type="owned",
                                        access_mode="api", region="test"))
            else:
                db.add(InferenceModel(slug="real/model", display_name="Real",
                                      backend_type="openai_compatible", context_length=8192,
                                      price_prompt_per_mtok_cents=15,
                                      price_completion_per_mtok_cents=45,
                                      cost_prompt_per_mtok_cents=5,
                                      cost_completion_per_mtok_cents=15))
            await db.commit()
            with pytest.raises(RuntimeError, match="Public demo refuses"):
                await require_mock_resources(db)
    finally:
        await engine.dispose()
