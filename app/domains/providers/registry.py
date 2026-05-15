from app.core.config import get_settings
from .base.provider import Provider
from .beltelecom.provider import BeltelecomProvider
from .fake import FakeProvider


class ProviderRegistry:
    def __init__(self, providers: list[Provider]) -> None:
        self._providers = {provider.code: provider for provider in providers}

    async def get(self, code: str) -> Provider | None:
        """Get provider by code"""
        try:
            return self._providers[code]
        except KeyError as exc:
            raise LookupError(f"Provider {code!r} is not registered") from exc

    async def list(self) -> list[str]:
        """List all registered providers (codes)"""
        return list(self._providers.keys())


settings = get_settings()


provider_registry = ProviderRegistry(
    [
        FakeProvider(),
        BeltelecomProvider(
            base_url=settings.beltelecom_base_url,
            username=settings.beltelecom_username,
            password=settings.beltelecom_password,
            timeout_sec=settings.beltelecom_timeout_sec,
        ),
    ]
)
