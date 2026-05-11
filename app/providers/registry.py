from app.providers.base import SmsProviderAdapter
from app.providers.fake import FakeSmsProviderAdapter


class ProviderRegistry:
    def __init__(self, adapters: list[SmsProviderAdapter]) -> None:
        self._adapters = {adapter.code: adapter for adapter in adapters}

    def get(self, code: str) -> SmsProviderAdapter:
        try:
            return self._adapters[code]
        except KeyError as exc:
            raise LookupError(f"Provider {code!r} is not registered") from exc

    def has(self, code: str) -> bool:
        return code in self._adapters


provider_registry = ProviderRegistry([FakeSmsProviderAdapter()])
