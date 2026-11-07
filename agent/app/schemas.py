from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeploymentCreateRequest(AgentModel):
    deployment_id: str = Field(
        min_length=5,
        max_length=48,
        pattern=r"^[a-z0-9][a-z0-9_-]+$",
    )
    model_id: str = Field(
        min_length=3,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]+$",
    )
    served_model_name: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^[a-z0-9][a-z0-9._/-]+$",
    )
    image: str | None = Field(default=None, max_length=240)
    gpu_device_ids: list[int] = Field(min_length=1, max_length=8)
    tensor_parallel_size: int = Field(default=1, ge=1, le=8)
    host_port: int = Field(ge=1024, le=65535)
    max_model_len: int | None = Field(default=None, ge=256, le=2_000_000)
    gpu_memory_utilization: float = Field(default=0.9, ge=0.1, le=0.98)
    huggingface_token_env_var: str | None = Field(
        default=None,
        max_length=120,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )
    vllm_api_key_env_var: str | None = Field(
        default=None,
        max_length=120,
        pattern=r"^[A-Z][A-Z0-9_]*$",
    )

    @field_validator("gpu_device_ids")
    @classmethod
    def unique_gpu_ids(cls, value: list[int]) -> list[int]:
        if any(item < 0 or item > 255 for item in value):
            raise ValueError("GPU device IDs must be between 0 and 255")
        if len(set(value)) != len(value):
            raise ValueError("GPU device IDs must be unique")
        return value

    @model_validator(mode="after")
    def validate_parallelism(self) -> "DeploymentCreateRequest":
        if self.tensor_parallel_size != len(self.gpu_device_ids):
            raise ValueError("tensor_parallel_size must equal the number of GPU device IDs")
        return self


class DeploymentResponse(AgentModel):
    deployment_id: str
    container_name: str
    model_id: str
    served_model_name: str
    image: str
    gpu_device_ids: list[int]
    host_port: int
    endpoint: str
    status: Literal[
        "creating",
        "running",
        "exited",
        "stopped",
        "removing",
        "absent",
        "unknown",
    ]
    exit_code: int | None = None


class GPUInfo(AgentModel):
    index: int
    name: str
    memory_total_mib: int


class NodeInfoResponse(AgentModel):
    docker_available: bool
    docker_version: str | None
    gpus: list[GPUInfo]
    agent_version: str = "0.1.0"
