import asyncio

from app.core.config import settings
from app.providers.base import ProviderConnection


class MockProvider:
    async def health_check(self) -> bool:
        return True

    async def create_instance(
        self, instance_id: str, *, idempotency_key: str
    ) -> ProviderConnection:
        await asyncio.sleep(settings.mock_provider_delay_seconds)
        suffix = instance_id[-6:]
        return ProviderConnection(
            provider_instance_id=f"mock-{suffix}",
            ssh_host=f"gpu-{suffix}.demo.open-compute-system.local",
            ssh_port=22022,
            jupyter_url=f"https://jupyter-{suffix}.demo.open-compute-system.local",
            credential_hint="演示凭据已托管，点击复制 SSH 命令",
        )

    async def start_instance(self, provider_id: str, *, idempotency_key: str) -> None:
        await asyncio.sleep(settings.mock_provider_delay_seconds)

    async def stop_instance(self, provider_id: str, *, idempotency_key: str) -> None:
        await asyncio.sleep(settings.mock_provider_delay_seconds)

    async def release_instance(self, provider_id: str, *, idempotency_key: str) -> None:
        await asyncio.sleep(settings.mock_provider_delay_seconds)
