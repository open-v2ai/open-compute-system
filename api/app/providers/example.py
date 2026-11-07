"""Template for a real ResourceProvider.

Copy this module, fill in the partner base URL and credentials from settings,
then register the access_mode in ``factory.py``. This class is not wired into
the factory; calling the methods raises ``NotImplementedError``.

Do not invent an API contract. Wait for the partner's official docs and a
sandbox account. Query retries are allowed; create/start/stop/release must
use the platform idempotency key and check real state before repeating a
write.
"""

from __future__ import annotations

from app.providers.base import ProviderConnection


class ExampleHttpProvider:
    def __init__(self, *, base_url: str, api_token: str) -> None:
        if not base_url or not api_token:
            raise ValueError("base_url and api_token are required")
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token

    async def health_check(self) -> bool:
        raise NotImplementedError(
            f"Wire GET {self._base_url}/health using the configured API token"
        )

    async def create_instance(
        self, instance_id: str, *, idempotency_key: str
    ) -> ProviderConnection:
        raise NotImplementedError(
            "POST create with Idempotency-Key; map host/port/jupyter into ProviderConnection"
        )

    async def start_instance(self, provider_id: str, *, idempotency_key: str) -> None:
        raise NotImplementedError("POST start; on timeout, GET status before retrying")

    async def stop_instance(self, provider_id: str, *, idempotency_key: str) -> None:
        raise NotImplementedError("POST stop; never log passwords or private keys")

    async def release_instance(self, provider_id: str, *, idempotency_key: str) -> None:
        raise NotImplementedError("POST release; treat already-gone as success")
