from app.core.config import get_settings
from .base.provider import Provider
from .beltelecom.provider import BeltelecomProvider
from .fake import FakeProvider


class ProviderRegistry:
    def __init__(self, providers: list[Provider]) -> None:
        self._providers = {provider.code: provider for provider in providers}

    async def get(self, code: str) -> Provider:
        """Get provider by code"""
        try:
            return self._providers[code]
        except KeyError as exc:
            raise LookupError(f"Provider {code!r} is not registered") from exc

    def try_get(self, code: str) -> Provider | None:
        return self._providers.get(code)

    def has(self, code: str) -> bool:
        return code in self._providers


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
