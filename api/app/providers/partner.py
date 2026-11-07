from app.providers.base import ProviderConnection


class PartnerProvider:
    """Placeholder for the first real compute partner.

    Do not invent credentials or endpoints. Copy ``example.py`` after a sandbox
    account and official API contract exist, then replace this class or register
    a new access_mode in ``factory.py``.
    """

    async def health_check(self) -> bool:
        raise NotImplementedError("Partner API credentials are not configured")

    async def create_instance(
        self, instance_id: str, *, idempotency_key: str
    ) -> ProviderConnection:
        raise NotImplementedError("Partner API contract is not configured")

    async def start_instance(self, provider_id: str, *, idempotency_key: str) -> None:
        raise NotImplementedError("Partner API contract is not configured")

    async def stop_instance(self, provider_id: str, *, idempotency_key: str) -> None:
        raise NotImplementedError("Partner API contract is not configured")

    async def release_instance(self, provider_id: str, *, idempotency_key: str) -> None:
        raise NotImplementedError("Partner API contract is not configured")
