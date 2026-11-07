from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class ProviderConnection:
    provider_instance_id: str
    ssh_host: str
    ssh_port: int
    jupyter_url: str
    credential_hint: str


class ResourceProvider(Protocol):
    async def health_check(self) -> bool: ...

    async def create_instance(
        self, instance_id: str, *, idempotency_key: str
    ) -> ProviderConnection: ...

    async def start_instance(self, provider_id: str, *, idempotency_key: str) -> None: ...

    async def stop_instance(self, provider_id: str, *, idempotency_key: str) -> None: ...

    async def release_instance(self, provider_id: str, *, idempotency_key: str) -> None: ...
