from app.domains.providers.exceptions import (
    ProviderDisabledError,
    ProviderNotFoundError,
    ProviderNotImplementedError,
)
from app.domains.providers.registry import provider_registry
from app.domains.providers.repositories import ProviderRepository


async def assert_provider_available_for_mailing(
    repository: ProviderRepository,
    code: str,
) -> None:
    row = await repository.get_by_code(code)
    if row is None:
        raise ProviderNotFoundError(code)
    if not row.is_enabled:
        raise ProviderDisabledError(code)
    if not provider_registry.has(code):
        raise ProviderNotImplementedError(code)
