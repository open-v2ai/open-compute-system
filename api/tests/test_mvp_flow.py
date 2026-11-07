import asyncio
import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import AdminUser, OutboxEvent
from app.services.instances import _record_provider_failure
from app.services.outbox import dispatch_outbox_once


def csrf_headers(client: TestClient, **headers: str) -> dict[str, str]:
    token = client.cookies.get(settings.csrf_cookie)
    assert token
    return {"X-CSRF-Token": token, **headers}


async def create_admin(username: str, role: str) -> None:
    async with SessionLocal() as db:
        db.add(
            AdminUser(
                username=username,
                password_hash=hash_password("RoleTest123"),
                display_name=f"{role} 测试",
                role=role,
                mfa_enabled=True,
            )
        )
        await db.commit()


async def recover_publishing_event(task_id: str) -> None:
    async with SessionLocal() as db:
        event = await db.scalar(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == task_id)
        )
        assert event
        event.status = "publishing"
        event.lease_expires_at = None
        await db.commit()
    assert await dispatch_outbox_once() >= 1
    async with SessionLocal() as db:
        recovered = await db.scalar(
            select(OutboxEvent).where(OutboxEvent.aggregate_id == task_id)
        )
        assert recovered and recovered.status == "published"


def login_user(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"phone": "13800138000", "password": "Demo12345"},
    )
    assert response.status_code == 200


def login_admin(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/auth/login",
        json={"username": "admin", "password": "Admin12345", "mfa_code": "123456"},
    )
    assert response.status_code == 200


def wait_for_instance(client: TestClient, instance_id: str, expected: str) -> dict:
    for _ in range(30):
        response = client.get(f"/api/v1/instances/{instance_id}")
        assert response.status_code == 200
        instance = response.json()
        if instance["status"] == expected:
            return instance
        time.sleep(0.03)
    raise AssertionError(f"instance {instance_id} did not reach {expected}")


def test_public_market_hides_sensitive_cost(client: TestClient) -> None:
    response = client.get("/api/v1/market/skus")
    assert response.status_code == 200
    assert response.json()
    assert "cost_hour_cents" not in response.json()[0]


def test_self_registration_can_be_disabled(client: TestClient) -> None:
    settings.self_registration_enabled = False
    try:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "phone": "13900000001",
                "password": "Disabled123",
                "nickname": "禁用注册",
                "accepted_terms": True,
            },
        )
    finally:
        settings.self_registration_enabled = True
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "SELF_REGISTRATION_DISABLED"


def test_user_instance_lifecycle_and_idempotency(client: TestClient) -> None:
    login_user(client)
    balance_before = client.get("/api/v1/auth/me").json()["balance_cents"]
    sku = next(
        item
        for item in client.get("/api/v1/market/skus").json()
        if item["inventory_available"]
    )
    key = f"pytest-{uuid.uuid4()}"
    payload = {
        "sku_id": sku["id"],
        "name": "pytest-gpu",
        "image": "PyTorch 2.7 · CUDA 12.8",
        "billing_mode": "hourly",
    }
    first = client.post(
        "/api/v1/instances",
        headers=csrf_headers(client, **{"Idempotency-Key": key}),
        json=payload,
    )
    second = client.post(
        "/api/v1/instances",
        headers=csrf_headers(client, **{"Idempotency-Key": key}),
        json=payload,
    )
    assert first.status_code == second.status_code == 202
    assert first.json()["instance_id"] == second.json()["instance_id"]
    balance_after = client.get("/api/v1/auth/me").json()["balance_cents"]
    assert balance_after == balance_before - sku["price_hour_cents"]
    transactions = client.get("/api/v1/wallet/transactions").json()
    assert sum(row["amount_cents"] for row in transactions) == -sku["price_hour_cents"]

    instance_id = first.json()["instance_id"]
    instance = wait_for_instance(client, instance_id, "running")
    assert instance["ssh_host"]
    assert instance["jupyter_url"]

    stop = client.post(
        f"/api/v1/instances/{instance_id}/stop",
        headers=csrf_headers(client, **{"Idempotency-Key": f"stop-{uuid.uuid4()}"}),
    )
    assert stop.status_code == 202
    wait_for_instance(client, instance_id, "stopped")

    start = client.post(
        f"/api/v1/instances/{instance_id}/start",
        headers=csrf_headers(client, **{"Idempotency-Key": f"start-{uuid.uuid4()}"}),
    )
    assert start.status_code == 202
    wait_for_instance(client, instance_id, "running")

    client.post(
        f"/api/v1/instances/{instance_id}/stop",
        headers=csrf_headers(client, **{"Idempotency-Key": f"stop-{uuid.uuid4()}"}),
    )
    wait_for_instance(client, instance_id, "stopped")
    release = client.post(
        f"/api/v1/instances/{instance_id}/release",
        headers=csrf_headers(client, **{"Idempotency-Key": f"release-{uuid.uuid4()}"}),
    )
    assert release.status_code == 202
    wait_for_instance(client, instance_id, "released")


def test_admin_permissions_cost_and_audit(client: TestClient) -> None:
    assert client.get("/api/v1/admin/skus").status_code == 401
    login_admin(client)
    skus = client.get("/api/v1/admin/skus")
    assert skus.status_code == 200
    assert "cost_hour_cents" in skus.json()[0]
    audit = client.get("/api/v1/admin/audit-logs")
    assert audit.status_code == 200
    assert any(row["action"] == "admin.login" for row in audit.json())


def test_lead_endpoints_removed(client: TestClient) -> None:
    created = client.post(
        "/api/v1/leads",
        json={
            "lead_type": "bare_metal",
            "source_page": "/market/bare-metal",
            "name": "测试客户",
            "contact": "wx-removed",
            "organization": "测试实验室",
            "product": "8 × H20",
            "requirement": "需要 8 卡整机进行模型训练",
        },
    )
    assert created.status_code == 404
    login_admin(client)
    assert client.get("/api/v1/admin/leads").status_code == 404


def test_idempotency_conflict_and_action_replay(client: TestClient) -> None:
    login_user(client)
    sku = next(
        item
        for item in client.get("/api/v1/market/skus").json()
        if item["inventory_available"]
    )
    create_key = f"conflict-{uuid.uuid4()}"
    payload = {"sku_id": sku["id"], "name": "idem-one", "billing_mode": "hourly"}
    first = client.post(
        "/api/v1/instances",
        headers=csrf_headers(client, **{"Idempotency-Key": create_key}),
        json=payload,
    )
    assert first.status_code == 202
    wait_for_instance(client, first.json()["instance_id"], "running")
    conflict = client.post(
        "/api/v1/instances",
        headers=csrf_headers(client, **{"Idempotency-Key": create_key}),
        json={**payload, "name": "idem-two"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"

    instance_id = first.json()["instance_id"]
    wait_for_instance(client, instance_id, "running")
    stop_key = f"stop-replay-{uuid.uuid4()}"
    stop_headers = csrf_headers(client, **{"Idempotency-Key": stop_key})
    stopped = client.post(f"/api/v1/instances/{instance_id}/stop", headers=stop_headers)
    assert stopped.status_code == 202
    wait_for_instance(client, instance_id, "stopped")
    replay = client.post(f"/api/v1/instances/{instance_id}/stop", headers=stop_headers)
    assert replay.status_code == 202
    assert replay.json()["id"] == stopped.json()["id"]


def test_csrf_rejects_missing_token_and_cross_origin(client: TestClient) -> None:
    login_user(client)
    sku = next(
        item
        for item in client.get("/api/v1/market/skus").json()
        if item["inventory_available"]
    )
    payload = {"sku_id": sku["id"], "name": "csrf-test", "billing_mode": "hourly"}
    missing = client.post(
        "/api/v1/instances", headers={"Idempotency-Key": str(uuid.uuid4())}, json=payload
    )
    assert missing.status_code == 403
    assert missing.json()["detail"]["code"] == "CSRF_TOKEN_INVALID"
    cross_origin = client.post(
        "/api/v1/instances",
        headers=csrf_headers(
            client,
            Origin="https://evil.example",
            **{"Idempotency-Key": str(uuid.uuid4())},
        ),
        json=payload,
    )
    assert cross_origin.status_code == 403
    assert cross_origin.json()["detail"]["code"] == "CSRF_ORIGIN_REJECTED"


def test_idempotency_key_is_scoped_to_actor(client: TestClient) -> None:
    login_user(client)
    sku = next(
        item
        for item in client.get("/api/v1/market/skus").json()
        if item["inventory_available"]
    )
    key = f"shared-{uuid.uuid4()}"
    payload = {"sku_id": sku["id"], "name": "first-actor", "billing_mode": "hourly"}
    first = client.post(
        "/api/v1/instances",
        headers=csrf_headers(client, **{"Idempotency-Key": key}),
        json=payload,
    )
    assert first.status_code == 202
    wait_for_instance(client, first.json()["instance_id"], "running")

    phone = f"139{int(uuid.uuid4().hex[:8], 16) % 100_000_000:08d}"
    registered = client.post(
        "/api/v1/auth/register",
        headers=csrf_headers(client),
        json={
            "phone": phone,
            "password": "ActorTest123",
            "nickname": "第二用户",
            "accepted_terms": True,
        },
    )
    assert registered.status_code == 201
    second = client.post(
        "/api/v1/instances",
        headers=csrf_headers(client, **{"Idempotency-Key": key}),
        json={**payload, "name": "second-actor"},
    )
    assert second.status_code == 202
    assert second.json()["instance_id"] != first.json()["instance_id"]
    wait_for_instance(client, second.json()["instance_id"], "running")


def test_provider_failure_refunds_balance_and_inventory(client: TestClient) -> None:
    login_user(client)
    sku = next(
        item
        for item in client.get("/api/v1/market/skus").json()
        if item["inventory_available"]
    )
    balance_before = client.get("/api/v1/auth/me").json()["balance_cents"]
    inventory_before = sku["inventory_available"]
    settings.demo_auto_dispatch = False
    try:
        created = client.post(
            "/api/v1/instances",
            headers=csrf_headers(client, **{"Idempotency-Key": f"fail-{uuid.uuid4()}"}),
            json={"sku_id": sku["id"], "name": "failed-create", "billing_mode": "hourly"},
        )
        assert created.status_code == 202
        task_id = created.json()["task_id"]
        for _ in range(settings.task_max_attempts):
            asyncio.run(_record_provider_failure(task_id, RuntimeError("provider unavailable")))
    finally:
        settings.demo_auto_dispatch = True

    assert client.get("/api/v1/auth/me").json()["balance_cents"] == balance_before
    current_sku = next(
        item for item in client.get("/api/v1/market/skus").json() if item["id"] == sku["id"]
    )
    assert current_sku["inventory_available"] == inventory_before
    order = client.get("/api/v1/orders").json()[0]
    assert order["status"] == "failed"


def test_outbox_recovers_abandoned_publishing_event(client: TestClient) -> None:
    login_user(client)
    sku = next(
        item
        for item in client.get("/api/v1/market/skus").json()
        if item["inventory_available"]
    )
    settings.demo_auto_dispatch = False
    try:
        created = client.post(
            "/api/v1/instances",
            headers=csrf_headers(client, **{"Idempotency-Key": f"outbox-{uuid.uuid4()}"}),
            json={"sku_id": sku["id"], "name": "outbox-recovery", "billing_mode": "hourly"},
        )
        assert created.status_code == 202
        asyncio.run(recover_publishing_event(created.json()["task_id"]))
    finally:
        settings.demo_auto_dispatch = True
    instance = client.get(f"/api/v1/instances/{created.json()['instance_id']}")
    assert instance.status_code == 200
    assert instance.json()["status"] == "running"


def test_support_role_is_read_only_and_cannot_see_balances_or_costs(client: TestClient) -> None:
    username = f"support-{uuid.uuid4().hex[:8]}"
    asyncio.run(create_admin(username, "support"))
    login = client.post(
        "/api/v1/admin/auth/login",
        json={"username": username, "password": "RoleTest123", "mfa_code": "123456"},
    )
    assert login.status_code == 200
    assert "catalog.manage" not in login.json()["permissions"]
    users = client.get("/api/v1/admin/users")
    assert users.status_code == 200
    assert all(row["balance_cents"] is None for row in users.json())
    skus = client.get("/api/v1/admin/skus")
    assert skus.status_code == 200
    assert all(row["cost_hour_cents"] is None for row in skus.json())
    forbidden = client.patch(
        f"/api/v1/admin/skus/{skus.json()[0]['id']}",
        headers=csrf_headers(client),
        json={"version": skus.json()[0]["version"], "status": "unpublished"},
    )
    assert forbidden.status_code == 403
