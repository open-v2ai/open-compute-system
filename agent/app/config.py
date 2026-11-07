from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_AGENT_TOKEN = "open-compute-agent-local-development-token"


class AgentSettings(BaseSettings):
    agent_env: Literal["development", "test", "production"] = "development"
    agent_token: SecretStr = SecretStr(LOCAL_AGENT_TOKEN)
    trusted_hosts: str = "localhost,127.0.0.1,testserver"
    docker_binary: str = "docker"
    nvidia_smi_binary: str = "nvidia-smi"
    vllm_default_image: str = "vllm/vllm-openai:latest"
    vllm_image_allowlist: str = "vllm/vllm-openai:"
    model_cache_dir: Path = Path("/var/lib/open-compute-agent/huggingface")
    vllm_bind_host: str = "127.0.0.1"
    vllm_advertised_host: str = "127.0.0.1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("agent_token")
    @classmethod
    def validate_token(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("AGENT_TOKEN must contain at least 32 characters")
        return value

    @model_validator(mode="after")
    def validate_production(self) -> "AgentSettings":
        if (
            self.agent_env == "production"
            and self.agent_token.get_secret_value() == LOCAL_AGENT_TOKEN
        ):
            raise ValueError("AGENT_TOKEN must be explicitly configured in production")
        if self.agent_env == "production" and self.vllm_bind_host == "0.0.0.0":
            # Public binding can be valid on a firewalled private node, but must be explicit.
            if "*" in self.allowed_hosts:
                raise ValueError("TRUSTED_HOSTS must be explicit when VLLM binds all interfaces")
        return self

    @property
    def allowed_hosts(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]

    @property
    def allowed_image_prefixes(self) -> list[str]:
        return [
            prefix.strip()
            for prefix in self.vllm_image_allowlist.split(",")
            if prefix.strip()
        ]


@lru_cache
def get_settings() -> AgentSettings:
    return AgentSettings()
