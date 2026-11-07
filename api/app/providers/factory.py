from app.core.config import settings
from app.models import ResourceProvider as ResourceProviderModel
from app.providers.base import ResourceProvider
from app.providers.mock import MockProvider
from app.providers.partner import PartnerProvider

# New access modes: copy example.py, implement the partner contract, then add a branch here.


def provider_for(resource: ResourceProviderModel | None) -> ResourceProvider:
    if resource is None:
        if settings.app_env == "production":
            raise ValueError("Production SKU is missing a configured resource provider")
        return MockProvider()
    if resource.access_mode == "mock":
        if settings.app_env == "production" and not settings.allow_mock_provider_in_production:
            raise ValueError("MockProvider is disabled in production")
        return MockProvider()
    if resource.access_mode == "api":
        return PartnerProvider()
    raise ValueError(f"Unsupported provider access mode: {resource.access_mode}")
