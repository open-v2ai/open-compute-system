import uuid

from fastapi.testclient import TestClient

from app.core.config import settings


def csrf_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(settings.csrf_cookie)
    assert token
    return {"X-CSRF-Token": token}


def test_registration_requires_exactly_one_unique_identity(client: TestClient) -> None:
    suffix = uuid.uuid4().hex[:10]
    phone = f"139{uuid.uuid4().int % 100_000_000:08d}"
    common = {
        "password": "Identity123",
        "nickname": "身份测试",
        "accepted_terms": True,
    }
    missing = client.post("/api/v1/auth/register", json=common)
    both = client.post(
        "/api/v1/auth/register",
        json={**common, "phone": phone, "email": f"both-{suffix}@example.com"},
    )
    assert missing.status_code == 422
    assert both.status_code == 422

    invite_code = client.post(
        "/api/v1/auth/register",
        json={**common, "email": f"invite-{suffix}@example.com", "invite_code": "REMOVED"},
    )
    assert invite_code.status_code == 422

    email = f"User-{suffix}@Example.com"
    email_registration = client.post(
        "/api/v1/auth/register",
        json={**common, "email": email},
    )
    assert email_registration.status_code == 201
    assert email_registration.json()["email"] == email.casefold()
    assert email_registration.json()["phone"] is None

    client.cookies.clear()
    email_login = client.post(
        "/api/v1/auth/login",
        json={"email": email.upper(), "password": common["password"]},
    )
    assert email_login.status_code == 200
    assert email_login.json()["id"] == email_registration.json()["id"]

    client.cookies.clear()
    phone_registration = client.post(
        "/api/v1/auth/register",
        json={**common, "phone": phone},
    )
    assert phone_registration.status_code == 201
    assert phone_registration.json()["phone"] == phone
    assert phone_registration.json()["email"] is None


def test_user_can_bind_and_unbind_identities_without_changing_user_id(
    client: TestClient,
) -> None:
    suffix = uuid.uuid4().hex[:10]
    password = "Binding123"
    email = f"binding-{suffix}@example.com"
    phone = f"137{uuid.uuid4().int % 100_000_000:08d}"
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "nickname": "绑定测试",
            "accepted_terms": True,
        },
    )
    assert registered.status_code == 201
    user_id = registered.json()["id"]

    last_identity = client.request(
        "DELETE",
        "/api/v1/auth/identities/email",
        headers=csrf_headers(client),
        json={"current_password": password},
    )
    assert last_identity.status_code == 409
    assert last_identity.json()["detail"]["code"] == "LAST_IDENTITY_REQUIRED"

    wrong_password = client.post(
        "/api/v1/auth/identities",
        headers=csrf_headers(client),
        json={"phone": phone, "current_password": "Wrong123"},
    )
    assert wrong_password.status_code == 401

    duplicate = client.post(
        "/api/v1/auth/identities",
        headers=csrf_headers(client),
        json={"phone": "13800138000", "current_password": password},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "IDENTITY_ALREADY_BOUND"

    bound = client.post(
        "/api/v1/auth/identities",
        headers=csrf_headers(client),
        json={"phone": phone, "current_password": password},
    )
    assert bound.status_code == 200
    assert bound.json()["id"] == user_id
    assert bound.json()["phone"] == phone
    assert bound.json()["email"] == email

    replacement = client.post(
        "/api/v1/auth/identities",
        headers=csrf_headers(client),
        json={"phone": "13600136000", "current_password": password},
    )
    assert replacement.status_code == 409
    assert replacement.json()["detail"]["code"] == "IDENTITY_TYPE_ALREADY_BOUND"

    unbound = client.request(
        "DELETE",
        "/api/v1/auth/identities/email",
        headers=csrf_headers(client),
        json={"current_password": password},
    )
    assert unbound.status_code == 200
    assert unbound.json()["id"] == user_id
    assert unbound.json()["email"] is None
    assert unbound.json()["phone"] == phone

    client.cookies.clear()
    assert client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).status_code == 401
    phone_login = client.post(
        "/api/v1/auth/login",
        json={"phone": phone, "password": password},
    )
    assert phone_login.status_code == 200
    assert phone_login.json()["id"] == user_id
