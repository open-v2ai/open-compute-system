import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.config import AgentSettings
from app.main import create_app
from app.runtime import CommandResult, DockerVLLMRuntime

TOKEN = "test-agent-token-with-at-least-32-characters"


class FakeRunner:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self.commands: list[list[str]] = []

    async def run(
        self,
        argv: list[str],
        *,
        timeout_seconds: int,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        del timeout_seconds, env
        self.commands.append(argv)
        if argv[1] == "inspect":
            row = self.rows.get(argv[2])
            if row is None:
                return CommandResult(1, stderr="No such object")
            return CommandResult(0, stdout=json.dumps([row]))
        if argv[1] == "run":
            name = argv[argv.index("--name") + 1]
            labels = {}
            for index, value in enumerate(argv):
                if value == "--label":
                    key, label_value = argv[index + 1].split("=", 1)
                    labels[key] = label_value
            image_index = argv.index("--env") + 2 if "--env" in argv else argv.index("--label")
            image = next(
                value
                for value in argv[image_index:]
                if value.startswith("vllm/vllm-openai:")
            )
            self.rows[name] = {
                "Config": {"Image": image, "Labels": labels},
                "State": {"Running": True, "Status": "running", "ExitCode": 0},
            }
            return CommandResult(0, stdout="container-id")
        if argv[1:3] == ["rm", "--force"]:
            self.rows.pop(argv[3], None)
            return CommandResult(0)
        if argv[1] == "version":
            return CommandResult(0, stdout="27.0.0\n")
        if argv[0] == "nvidia-smi":
            return CommandResult(0, stdout="0, NVIDIA RTX 4090, 24564\n")
        raise AssertionError(f"Unexpected command: {argv}")


def make_client(tmp_path: Path) -> tuple[TestClient, FakeRunner]:
    settings = AgentSettings(
        agent_token=SecretStr(TOKEN),
        trusted_hosts="testserver",
        model_cache_dir=tmp_path / "cache",
        vllm_advertised_host="10.0.0.8",
    )
    runner = FakeRunner()
    runtime = DockerVLLMRuntime(settings, runner)
    return TestClient(create_app(settings=settings, runtime=runtime)), runner


def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def payload() -> dict:
    return {
        "deployment_id": "dep_qwen3_8b",
        "model_id": "Qwen/Qwen3-8B",
        "served_model_name": "customer/qwen3-8b",
        "gpu_device_ids": [0],
        "tensor_parallel_size": 1,
        "host_port": 18080,
        "max_model_len": 8192,
    }


def test_agent_settings_reject_unknown_environment_name() -> None:
    with pytest.raises(ValidationError):
        AgentSettings(agent_env="prodution", agent_token=SecretStr(TOKEN))


def test_agent_requires_token(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    assert client.get("/v1/node").status_code == 401
    assert client.get("/v1/node", headers=auth()).status_code == 200


def test_create_is_idempotent_and_uses_fixed_docker_arguments(tmp_path: Path) -> None:
    client, runner = make_client(tmp_path)
    first = client.post("/v1/deployments", headers=auth(), json=payload())
    assert first.status_code == 201
    assert first.json()["status"] == "running"
    assert first.json()["endpoint"] == "http://10.0.0.8:18080/v1"
    second = client.post("/v1/deployments", headers=auth(), json=payload())
    assert second.status_code == 201
    run_commands = [command for command in runner.commands if command[1] == "run"]
    assert len(run_commands) == 1
    command = run_commands[0]
    assert command[0:2] == ["docker", "run"]
    assert "--privileged" not in command
    assert "Qwen/Qwen3-8B" in command


def test_same_deployment_id_rejects_changed_configuration(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    assert client.post("/v1/deployments", headers=auth(), json=payload()).status_code == 201
    changed = payload()
    changed["host_port"] = 18081
    response = client.post("/v1/deployments", headers=auth(), json=changed)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "DEPLOYMENT_CONFLICT"


def test_same_deployment_id_rejects_changed_credential_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HF_TOKEN_PRIMARY", "primary-secret")
    monkeypatch.setenv("HF_TOKEN_SECONDARY", "secondary-secret")
    client, _ = make_client(tmp_path)
    initial = {**payload(), "huggingface_token_env_var": "HF_TOKEN_PRIMARY"}
    assert client.post("/v1/deployments", headers=auth(), json=initial).status_code == 201

    changed = {**payload(), "huggingface_token_env_var": "HF_TOKEN_SECONDARY"}
    response = client.post("/v1/deployments", headers=auth(), json=changed)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "DEPLOYMENT_CONFLICT"


def test_remove_only_managed_container(tmp_path: Path) -> None:
    client, _ = make_client(tmp_path)
    assert client.post("/v1/deployments", headers=auth(), json=payload()).status_code == 201
    removed = client.delete("/v1/deployments/dep_qwen3_8b", headers=auth())
    assert removed.status_code == 200
    assert removed.json()["status"] == "absent"
