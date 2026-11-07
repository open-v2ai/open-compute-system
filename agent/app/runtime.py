from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.config import AgentSettings
from app.schemas import DeploymentCreateRequest, DeploymentResponse, GPUInfo, NodeInfoResponse


class RuntimeErrorBase(RuntimeError):
    code = "AGENT_RUNTIME_ERROR"


class DockerUnavailableError(RuntimeErrorBase):
    code = "DOCKER_UNAVAILABLE"


class DeploymentConflictError(RuntimeErrorBase):
    code = "DEPLOYMENT_CONFLICT"


class DeploymentOperationError(RuntimeErrorBase):
    code = "DEPLOYMENT_OPERATION_FAILED"


@dataclass(slots=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class CommandRunner(Protocol):
    async def run(
        self,
        argv: list[str],
        *,
        timeout_seconds: int,
        env: dict[str, str] | None = None,
    ) -> CommandResult: ...


class SubprocessCommandRunner:
    async def run(
        self,
        argv: list[str],
        *,
        timeout_seconds: int,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        def execute() -> CommandResult:
            try:
                completed = subprocess.run(
                    argv,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    env=env,
                    shell=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise DockerUnavailableError("Docker command could not be executed") from exc
            return CommandResult(
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )

        return await asyncio.to_thread(execute)


class DockerVLLMRuntime:
    def __init__(
        self,
        settings: AgentSettings,
        runner: CommandRunner | None = None,
    ) -> None:
        self.settings = settings
        self.runner = runner or SubprocessCommandRunner()

    def _container_name(self, deployment_id: str) -> str:
        return f"ocs-vllm-{deployment_id}"

    def _endpoint(self, host_port: int) -> str:
        return f"http://{self.settings.vllm_advertised_host}:{host_port}/v1"

    def _image(self, requested: str | None) -> str:
        image = requested or self.settings.vllm_default_image
        if not any(image.startswith(prefix) for prefix in self.settings.allowed_image_prefixes):
            raise DeploymentOperationError("vLLM image is not allowlisted")
        return image

    @staticmethod
    def _config_hash(payload: DeploymentCreateRequest, image: str) -> str:
        # Environment variable names are deployment configuration, not secret values. Including
        # them prevents an idempotent replay from silently retaining a stale credential source.
        value = payload.model_dump()
        value["image"] = image
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()

    async def _inspect(self, container_name: str) -> dict | None:
        result = await self.runner.run(
            [self.settings.docker_binary, "inspect", container_name],
            timeout_seconds=15,
        )
        if result.returncode != 0:
            if "No such" in result.stderr or "not found" in result.stderr.lower():
                return None
            raise DockerUnavailableError("Docker inspect failed")
        try:
            rows = json.loads(result.stdout)
            return rows[0]
        except (IndexError, TypeError, json.JSONDecodeError) as exc:
            raise DockerUnavailableError("Docker returned invalid inspect data") from exc

    def _response_from_inspect(
        self,
        deployment_id: str,
        row: dict | None,
    ) -> DeploymentResponse:
        if row is None:
            return DeploymentResponse(
                deployment_id=deployment_id,
                container_name=self._container_name(deployment_id),
                model_id="",
                served_model_name="",
                image="",
                gpu_device_ids=[],
                host_port=0,
                endpoint="",
                status="absent",
            )
        labels = row.get("Config", {}).get("Labels", {}) or {}
        state = row.get("State", {}) or {}
        running = bool(state.get("Running"))
        raw_status = str(state.get("Status", "unknown"))
        status = "running" if running else raw_status
        if status not in {"creating", "running", "exited", "stopped", "removing"}:
            status = "unknown"
        host_port = int(labels.get("ocs.host_port", "0"))
        gpu_ids = [
            int(item)
            for item in labels.get("ocs.gpu_device_ids", "").split(",")
            if item.isdigit()
        ]
        return DeploymentResponse(
            deployment_id=deployment_id,
            container_name=self._container_name(deployment_id),
            model_id=labels.get("ocs.model_id", ""),
            served_model_name=labels.get("ocs.served_model_name", ""),
            image=row.get("Config", {}).get("Image", ""),
            gpu_device_ids=gpu_ids,
            host_port=host_port,
            endpoint=self._endpoint(host_port) if host_port else "",
            status=status,
            exit_code=state.get("ExitCode"),
        )

    async def get_deployment(self, deployment_id: str) -> DeploymentResponse:
        row = await self._inspect(self._container_name(deployment_id))
        return self._response_from_inspect(deployment_id, row)

    async def create_deployment(
        self,
        payload: DeploymentCreateRequest,
    ) -> DeploymentResponse:
        image = self._image(payload.image)
        config_hash = self._config_hash(payload, image)
        container_name = self._container_name(payload.deployment_id)
        existing = await self._inspect(container_name)
        if existing is not None:
            labels = existing.get("Config", {}).get("Labels", {}) or {}
            if labels.get("ocs.config_hash") != config_hash:
                raise DeploymentConflictError("Deployment ID already uses different settings")
            return self._response_from_inspect(payload.deployment_id, existing)

        cache_dir: Path = self.settings.model_cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        gpu_ids = ",".join(str(item) for item in payload.gpu_device_ids)
        argv = [
            self.settings.docker_binary,
            "run",
            "-d",
            "--name",
            container_name,
            "--restart",
            "unless-stopped",
            "--gpus",
            f"device={gpu_ids}",
            "--publish",
            f"{self.settings.vllm_bind_host}:{payload.host_port}:8000",
            "--volume",
            f"{cache_dir}:/root/.cache/huggingface",
            "--label",
            "ocs.managed=true",
            "--label",
            f"ocs.deployment_id={payload.deployment_id}",
            "--label",
            f"ocs.config_hash={config_hash}",
            "--label",
            f"ocs.model_id={payload.model_id}",
            "--label",
            f"ocs.served_model_name={payload.served_model_name}",
            "--label",
            f"ocs.gpu_device_ids={gpu_ids}",
            "--label",
            f"ocs.host_port={payload.host_port}",
        ]
        child_env = os.environ.copy()
        if payload.huggingface_token_env_var:
            token = os.environ.get(payload.huggingface_token_env_var)
            if not token:
                raise DeploymentOperationError("Hugging Face token environment variable is missing")
            child_env["HF_TOKEN"] = token
            argv.extend(["--env", "HF_TOKEN"])
        if payload.vllm_api_key_env_var:
            api_key = os.environ.get(payload.vllm_api_key_env_var)
            if not api_key:
                raise DeploymentOperationError("vLLM API key environment variable is missing")
            child_env["VLLM_API_KEY"] = api_key
            argv.extend(["--env", "VLLM_API_KEY"])
        argv.extend(
            [
                image,
                "--model",
                payload.model_id,
                "--served-model-name",
                payload.served_model_name,
                "--tensor-parallel-size",
                str(payload.tensor_parallel_size),
                "--gpu-memory-utilization",
                str(payload.gpu_memory_utilization),
            ]
        )
        if payload.max_model_len is not None:
            argv.extend(["--max-model-len", str(payload.max_model_len)])

        result = await self.runner.run(
            argv,
            timeout_seconds=120,
            env=child_env,
        )
        if result.returncode != 0:
            raise DeploymentOperationError("Docker could not start the vLLM container")
        row = await self._inspect(container_name)
        if row is None:
            raise DeploymentOperationError("Docker started no inspectable container")
        return self._response_from_inspect(payload.deployment_id, row)

    async def remove_deployment(self, deployment_id: str) -> DeploymentResponse:
        container_name = self._container_name(deployment_id)
        existing = await self._inspect(container_name)
        if existing is None:
            return self._response_from_inspect(deployment_id, None)
        labels = existing.get("Config", {}).get("Labels", {}) or {}
        if labels.get("ocs.managed") != "true":
            raise DeploymentConflictError("Container is not managed by this agent")
        result = await self.runner.run(
            [self.settings.docker_binary, "rm", "--force", container_name],
            timeout_seconds=60,
        )
        if result.returncode != 0:
            raise DeploymentOperationError("Docker could not remove the deployment")
        return self._response_from_inspect(deployment_id, None)

    async def node_info(self) -> NodeInfoResponse:
        version = await self.runner.run(
            [self.settings.docker_binary, "version", "--format", "{{.Server.Version}}"],
            timeout_seconds=15,
        )
        if version.returncode != 0:
            return NodeInfoResponse(docker_available=False, docker_version=None, gpus=[])
        try:
            gpu_result = await self.runner.run(
                [
                    self.settings.nvidia_smi_binary,
                    "--query-gpu=index,name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                timeout_seconds=15,
            )
        except DockerUnavailableError:
            gpu_result = CommandResult(returncode=127)
        gpus: list[GPUInfo] = []
        if gpu_result.returncode == 0:
            for line in gpu_result.stdout.splitlines():
                parts = [part.strip() for part in line.split(",", 2)]
                if len(parts) != 3:
                    continue
                try:
                    gpus.append(
                        GPUInfo(
                            index=int(parts[0]),
                            name=parts[1],
                            memory_total_mib=int(parts[2]),
                        )
                    )
                except ValueError:
                    continue
        return NodeInfoResponse(
            docker_available=True,
            docker_version=version.stdout.strip() or None,
            gpus=gpus,
        )
