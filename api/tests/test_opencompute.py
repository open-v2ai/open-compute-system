"""Open Compute System inference gateway and wallet tests."""

from fastapi.testclient import TestClient

from app.core.config import settings


def csrf_headers(client: TestClient, **headers: str) -> dict[str, str]:
    token = client.cookies.get(settings.csrf_cookie)
    assert token
    return {"X-CSRF-Token": token, **headers}


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


def test_public_inference_catalog_hides_cost(client: TestClient) -> None:
    response = client.get("/api/v1/inference/models")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 2
    assert "cost_prompt_per_mtok_cents" not in rows[0]
    assert rows[0]["slug"].startswith("opencompute/")


def test_openai_models_list(client: TestClient) -> None:
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert any(item["id"] == "opencompute/qwen3-8b" for item in body["data"])


def test_api_key_chat_completion_and_idempotency(client: TestClient) -> None:
    login_user(client)
    before = client.get("/api/v1/auth/me").json()["balance_cents"]
    created = client.post(
        "/api/v1/inference/keys",
        headers=csrf_headers(client),
        json={"name": "test-key"},
    )
    assert created.status_code == 201
    secret = created.json()["secret"]
    assert secret.startswith("ocs_")

    request_id = "req_test_idem_001"
    payload = {
        "model": "opencompute/qwen3-8b",
        "messages": [{"role": "user", "content": "hello opencompute"}],
        "max_tokens": 64,
    }
    first = client.post(
        "/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {secret}", "X-Request-ID": request_id},
        json=payload,
    )
    assert first.status_code == 200
    body = first.json()
    assert body["choices"][0]["message"]["content"]
    assert body["usage"]["total_tokens"] > 0

    second = client.post(
        "/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {secret}", "X-Request-ID": request_id},
        json=payload,
    )
    assert second.status_code == 200
    assert second.json()["id"] == body["id"]

    after = client.get("/api/v1/auth/me").json()["balance_cents"]
    assert after <= before

    usage = client.get("/api/v1/inference/usage")
    assert usage.status_code == 200
    assert any(row["request_id"] == request_id for row in usage.json())


def test_chat_completion_uses_sanitized_request_id(client: TestClient) -> None:
    login_user(client)
    created = client.post(
        "/api/v1/inference/keys",
        headers=csrf_headers(client),
        json={"name": "sanitized-request-id"},
    )
    secret = created.json()["secret"]
    invalid_request_id = "x" * 81

    response = client.post(
        "/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {secret}", "X-Request-ID": invalid_request_id},
        json={
            "model": "opencompute/qwen3-8b",
            "messages": [{"role": "user", "content": "sanitize this request ID"}],
            "max_tokens": 16,
        },
    )

    assert response.status_code == 200
    sanitized_request_id = response.headers["X-Request-ID"]
    assert sanitized_request_id != invalid_request_id
    assert len(sanitized_request_id) <= 80
    usage = client.get("/api/v1/inference/usage").json()
    assert any(row["request_id"] == sanitized_request_id for row in usage)


def test_auto_router_uses_classifier_for_simple_and_complex_requests(
    client: TestClient,
) -> None:
    login_user(client)
    created = client.post(
        "/api/v1/inference/keys",
        headers=csrf_headers(client),
        json={"name": "auto-only", "allowed_models": ["opencompute/auto"]},
    )
    assert created.status_code == 201
    secret = created.json()["secret"]

    simple = client.post(
        "/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {secret}", "X-Request-ID": "req_auto_simple"},
        json={
            "model": "opencompute/auto",
            "messages": [{"role": "user", "content": "你好，今天星期几？"}],
            "max_tokens": 32,
        },
    )
    assert simple.status_code == 200
    assert simple.json()["model"] == "opencompute/auto"
    assert simple.json()["ocs_router"] == {
        "selected_model": "opencompute/qwen3-8b",
        "tier": "simple",
        "decision_source": "classifier",
    }

    complex_response = client.post(
        "/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {secret}", "X-Request-ID": "req_auto_complex"},
        json={
            "model": "opencompute/auto",
            "messages": [
                {
                    "role": "user",
                    "content": "请设计一个可重试且幂等的任务调度算法，并分析故障边界。",
                }
            ],
            "max_tokens": 64,
        },
    )
    assert complex_response.status_code == 200
    assert complex_response.json()["ocs_router"]["selected_model"] == (
        "opencompute/qwen3-32b"
    )
    assert complex_response.json()["ocs_router"]["tier"] == "complex"

    usage = client.get("/api/v1/inference/usage").json()
    simple_usage = next(row for row in usage if row["request_id"] == "req_auto_simple")
    assert simple_usage["model_slug"] == "opencompute/auto"
    assert simple_usage["routed_model_slug"] == "opencompute/qwen3-8b"
    assert simple_usage["classifier_model_slug"] == "opencompute/qwen3-8b"
    assert simple_usage["routing_decision_source"] == "classifier"


def test_auto_router_requires_configuration_before_publish(client: TestClient) -> None:
    login_admin(client)
    created = client.post(
        "/api/v1/admin/inference/models",
        headers=csrf_headers(client),
        json={
            "slug": "customer/unconfigured-auto",
            "display_name": "Unconfigured Auto",
            "description": "draft router",
            "context_length": 8192,
            "price_prompt_per_mtok_cents": 50,
            "price_completion_per_mtok_cents": 100,
            "cost_prompt_per_mtok_cents": 20,
            "cost_completion_per_mtok_cents": 40,
            "backend_type": "auto_router",
        },
    )
    assert created.status_code == 201
    model = created.json()
    published = client.patch(
        f"/api/v1/admin/inference/models/{model['id']}",
        headers=csrf_headers(client),
        json={"version": model["version"], "status": "published", "reason": "test"},
    )
    assert published.status_code == 422
    assert published.json()["detail"]["code"] == "AUTO_ROUTER_NOT_CONFIGURED"


def test_chat_conversation_persists(client: TestClient) -> None:
    login_user(client)
    created = client.post(
        "/api/v1/inference/conversations",
        headers=csrf_headers(client),
        json={"model_slug": "opencompute/qwen3-8b", "title": "新对话"},
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]
    sent = client.post(
        f"/api/v1/inference/conversations/{conversation_id}/messages",
        headers=csrf_headers(client),
        json={"content": "请介绍一下你自己"},
    )
    assert sent.status_code == 200
    payload = sent.json()
    assert payload["user_message"]["role"] == "user"
    assert payload["assistant_message"]["role"] == "assistant"
    detail = client.get(f"/api/v1/inference/conversations/{conversation_id}")
    assert detail.status_code == 200
    assert len(detail.json()["messages"]) >= 2


def test_insufficient_balance_returns_402(client: TestClient) -> None:
    import asyncio

    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import User

    login_user(client)
    created = client.post(
        "/api/v1/inference/keys",
        headers=csrf_headers(client),
        json={"name": "poor-key"},
    )
    secret = created.json()["secret"]

    async def set_balance(cents: int) -> None:
        async with SessionLocal() as db:
            user = await db.scalar(select(User).where(User.phone == "13800138000"))
            assert user
            user.balance_cents = cents
            user.inference_remainder_micros = 0
            await db.commit()

    asyncio.run(set_balance(0))
    try:
        response = client.post(
            "/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {secret}", "X-Request-ID": "req_no_money"},
            json={
                "model": "opencompute/qwen3-32b",
                "messages": [{"role": "user", "content": "x" * 200}],
                "max_tokens": 256,
            },
        )
        assert response.status_code == 402
        assert response.json()["detail"]["code"] == "INSUFFICIENT_BALANCE"
    finally:
        asyncio.run(set_balance(500_000))


def test_revoked_key_rejected(client: TestClient) -> None:
    login_user(client)
    created = client.post(
        "/api/v1/inference/keys",
        headers=csrf_headers(client),
        json={"name": "to-revoke"},
    )
    secret = created.json()["secret"]
    key_id = created.json()["id"]
    revoke = client.post(
        f"/api/v1/inference/keys/{key_id}/revoke",
        headers=csrf_headers(client),
    )
    assert revoke.status_code == 200
    response = client.post(
        "/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {secret}"},
        json={
            "model": "opencompute/qwen3-8b",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert response.status_code == 401


def test_admin_inference_cost_permission(client: TestClient) -> None:
    login_admin(client)
    response = client.get("/api/v1/admin/inference/models")
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert rows[0]["cost_prompt_per_mtok_cents"] is not None


def test_replica_failover(client: TestClient) -> None:
    login_user(client)
    created = client.post(
        "/api/v1/inference/keys",
        headers=csrf_headers(client),
        json={"name": "failover"},
    )
    secret = created.json()["secret"]

    import asyncio

    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import InferenceModel, InferenceReplica

    async def mark_fail() -> None:
        async with SessionLocal() as db:
            model = await db.scalar(
                select(InferenceModel).where(InferenceModel.slug == "opencompute/qwen3-8b")
            )
            assert model
            replica = await db.scalar(
                select(InferenceReplica).where(
                    InferenceReplica.model_id == model.id,
                    InferenceReplica.label == "mock-a",
                )
            )
            assert replica
            replica.fail_once = True
            await db.commit()

    asyncio.run(mark_fail())
    response = client.post(
        "/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {secret}", "X-Request-ID": "req_failover_1"},
        json={
            "model": "opencompute/qwen3-8b",
            "messages": [{"role": "user", "content": "failover please"}],
        },
    )
    assert response.status_code == 200
    usage = client.get("/api/v1/inference/usage").json()
    hit = next(row for row in usage if row["request_id"] == "req_failover_1")
    assert hit["replica_label"] == "mock-b"


def test_admin_can_publish_real_openai_compatible_model(
    client: TestClient, monkeypatch
) -> None:
    import httpx

    upstream_payload: dict = {}

    class FakeAsyncClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def get(self, _url: str, **_kwargs) -> httpx.Response:
            return httpx.Response(200, json={"object": "list", "data": []})

        async def post(self, _url: str, **kwargs) -> httpx.Response:
            upstream_payload.update(kwargs["json"])
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl_upstream",
                    "choices": [
                        {"message": {"role": "assistant", "content": "real endpoint reply"}}
                    ],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 7},
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    login_admin(client)
    model_response = client.post(
        "/api/v1/admin/inference/models",
        headers=csrf_headers(client),
        json={
            "slug": "customer/real-model",
            "display_name": "Customer Real Model",
            "description": "OpenAI compatible endpoint",
            "context_length": 8192,
            "price_prompt_per_mtok_cents": 20,
            "price_completion_per_mtok_cents": 50,
            "cost_prompt_per_mtok_cents": 10,
            "cost_completion_per_mtok_cents": 20,
            "backend_type": "openai_compatible",
        },
    )
    assert model_response.status_code == 201
    model = model_response.json()
    replica_response = client.post(
        f"/api/v1/admin/inference/models/{model['id']}/replicas",
        headers=csrf_headers(client),
        json={
            "label": "customer-a",
            "endpoint": "https://inference.internal/v1",
            "upstream_model": "qwen/customer-model",
            "timeout_seconds": 60,
            "capacity_tpm": 120000,
        },
    )
    assert replica_response.status_code == 201
    replica = replica_response.json()
    health = client.post(
        f"/api/v1/admin/inference/replicas/{replica['id']}/health-check",
        headers=csrf_headers(client),
    )
    assert health.status_code == 200
    assert health.json()["health_status"] == "healthy"
    published = client.patch(
        f"/api/v1/admin/inference/models/{model['id']}",
        headers=csrf_headers(client),
        json={"version": model["version"], "status": "published", "reason": "test"},
    )
    assert published.status_code == 200

    client.cookies.clear()
    login_user(client)
    created = client.post(
        "/api/v1/inference/keys",
        headers=csrf_headers(client),
        json={
            "name": "real-model-only",
            "rpm_limit": 10,
            "tpm_limit": 10000,
            "allowed_models": ["customer/real-model"],
        },
    )
    assert created.status_code == 201
    secret = created.json()["secret"]
    response = client.post(
        "/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {secret}", "X-Request-ID": "req_real_endpoint"},
        json={
            "model": "customer/real-model",
            "messages": [{"role": "user", "content": "hello"}],
            "max_tokens": 32,
            "temperature": 0.25,
        },
    )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "real endpoint reply"
    assert response.json()["usage"]["total_tokens"] == 18
    assert upstream_payload["temperature"] == 0.25


def test_api_key_rpm_limit_is_enforced(client: TestClient) -> None:
    login_user(client)
    created = client.post(
        "/api/v1/inference/keys",
        headers=csrf_headers(client),
        json={"name": "one-rpm", "rpm_limit": 1, "tpm_limit": 10000},
    )
    assert created.status_code == 201
    secret = created.json()["secret"]
    payload = {
        "model": "opencompute/qwen3-8b",
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 8,
    }
    first = client.post(
        "/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {secret}", "X-Request-ID": "req_rpm_first"},
        json=payload,
    )
    assert first.status_code == 200
    second = client.post(
        "/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {secret}", "X-Request-ID": "req_rpm_second"},
        json=payload,
    )
    assert second.status_code == 429
    assert second.json()["detail"]["code"] == "KEY_RPM_LIMIT"


def test_admin_can_deploy_vllm_through_private_node_agent(
    client: TestClient, monkeypatch
) -> None:
    import httpx

    agent_deployments: dict[str, dict] = {}
    agent_create_calls = 0

    class FakeAsyncClient:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def request(
            self,
            method: str,
            url: str,
            *,
            headers=None,
            json=None,
        ) -> httpx.Response:
            nonlocal agent_create_calls
            assert headers["Authorization"] == "Bearer agent-secret"
            if method == "GET" and url.endswith("/v1/node"):
                return httpx.Response(
                    200,
                    json={
                        "docker_available": True,
                        "docker_version": "27.0.0",
                        "gpus": [
                            {"index": 0, "name": "NVIDIA RTX 4090", "memory_total_mib": 24564}
                        ],
                        "agent_version": "0.1.0",
                    },
                )
            if method == "POST" and url.endswith("/v1/deployments"):
                agent_create_calls += 1
                deployment_id = json["deployment_id"]
                row = {
                    "deployment_id": deployment_id,
                    "container_name": f"ocs-vllm-{deployment_id}",
                    "model_id": json["model_id"],
                    "served_model_name": json["served_model_name"],
                    "image": "vllm/vllm-openai:latest",
                    "gpu_device_ids": json["gpu_device_ids"],
                    "host_port": json["host_port"],
                    "endpoint": f"http://10.0.0.8:{json['host_port']}/v1",
                    "status": "running",
                    "exit_code": 0,
                }
                agent_deployments[deployment_id] = row
                return httpx.Response(201, json=row)
            deployment_id = url.rsplit("/", 1)[-1]
            if method == "GET" and "/v1/deployments/" in url:
                return httpx.Response(200, json=agent_deployments[deployment_id])
            if method == "DELETE" and "/v1/deployments/" in url:
                row = agent_deployments.pop(deployment_id)
                return httpx.Response(
                    200,
                    json={
                        **row,
                        "model_id": "",
                        "served_model_name": "",
                        "image": "",
                        "gpu_device_ids": [],
                        "host_port": 0,
                        "endpoint": "",
                        "status": "absent",
                        "exit_code": None,
                    },
                )
            raise AssertionError(f"Unexpected agent request: {method} {url}")

        async def get(self, url: str, **_kwargs) -> httpx.Response:
            assert url.endswith("/v1/models")
            return httpx.Response(200, json={"object": "list", "data": []})

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setenv("TEST_AGENT_TOKEN", "agent-secret")
    monkeypatch.setenv("TEST_VLLM_INTERNAL_KEY", "vllm-secret")

    login_admin(client)
    model_response = client.post(
        "/api/v1/admin/inference/models",
        headers=csrf_headers(client),
        json={
            "slug": "customer/agent-model",
            "display_name": "Agent Managed Model",
            "context_length": 8192,
            "price_prompt_per_mtok_cents": 20,
            "price_completion_per_mtok_cents": 50,
            "cost_prompt_per_mtok_cents": 10,
            "cost_completion_per_mtok_cents": 20,
            "backend_type": "openai_compatible",
        },
    )
    assert model_response.status_code == 201
    model = model_response.json()

    node_response = client.post(
        "/api/v1/admin/inference/nodes",
        headers=csrf_headers(client),
        json={
            "name": "Private GPU Node",
            "agent_url": "http://10.0.0.8:8110",
            "agent_token_env_var": "TEST_AGENT_TOKEN",
            "runtime_credential_env_var": "TEST_VLLM_INTERNAL_KEY",
        },
    )
    assert node_response.status_code == 201
    node = node_response.json()
    health = client.post(
        f"/api/v1/admin/inference/nodes/{node['id']}/health-check",
        headers=csrf_headers(client),
    )
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    deployment_payload = {
        "model_id": model["id"],
        "node_id": node["id"],
        "model_source_id": "Qwen/Qwen3-8B",
        "served_model_name": "customer/agent-model",
        "gpu_device_ids": [0],
        "tensor_parallel_size": 1,
        "host_port": 18080,
        "max_model_len": 8192,
        "gpu_memory_utilization": 0.9,
    }

    import asyncio

    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import AdminUser, InferenceDeployment
    from app.schemas import InferenceDeploymentCreateRequest
    from app.services.inference_deployments import _request_hash

    async def seed_abandoned_deployment() -> str:
        request = InferenceDeploymentCreateRequest.model_validate(deployment_payload)
        async with SessionLocal() as db:
            admin = await db.scalar(select(AdminUser).where(AdminUser.username == "admin"))
            assert admin
            deployment = InferenceDeployment(
                created_by=admin.id,
                idempotency_key="deploy-agent-model-1",
                request_hash=_request_hash(request),
                model_id=request.model_id,
                node_id=request.node_id,
                model_source_id=request.model_source_id,
                served_model_name=request.served_model_name,
                image=request.image,
                gpu_device_ids=request.gpu_device_ids,
                tensor_parallel_size=request.tensor_parallel_size,
                host_port=request.host_port,
                max_model_len=request.max_model_len,
                gpu_memory_utilization_milli=round(request.gpu_memory_utilization * 1000),
                huggingface_token_env_var=request.huggingface_token_env_var,
                status="provisioning",
            )
            db.add(deployment)
            await db.commit()
            await db.refresh(deployment)
            return deployment.id

    abandoned_deployment_id = asyncio.run(seed_abandoned_deployment())
    deployment_response = client.post(
        "/api/v1/admin/inference/deployments",
        headers=csrf_headers(client, **{"Idempotency-Key": "deploy-agent-model-1"}),
        json=deployment_payload,
    )
    assert deployment_response.status_code == 202
    deployment = deployment_response.json()
    assert deployment["id"] == abandoned_deployment_id
    assert deployment["status"] == "provisioning"
    assert deployment["replica_id"]
    assert deployment["endpoint"] == "http://10.0.0.8:18080/v1"

    repeated = client.post(
        "/api/v1/admin/inference/deployments",
        headers=csrf_headers(client, **{"Idempotency-Key": "deploy-agent-model-1"}),
        json=deployment_payload,
    )
    assert repeated.status_code == 202
    assert repeated.json()["id"] == deployment["id"]
    assert agent_create_calls == 1

    synced = client.post(
        f"/api/v1/admin/inference/deployments/{deployment['id']}/sync",
        headers=csrf_headers(client),
    )
    assert synced.status_code == 200
    assert synced.json()["status"] == "running"

    stopped = client.post(
        f"/api/v1/admin/inference/deployments/{deployment['id']}/stop",
        headers=csrf_headers(client),
    )
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"
