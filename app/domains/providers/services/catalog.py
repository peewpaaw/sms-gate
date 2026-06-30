from app.domains.providers.models import Provider
from app.domains.providers.registry import provider_registry
from app.domains.providers.schemas import ProviderRead


def provider_to_read(row: Provider, *, require_impl: bool) -> ProviderRead | None:
    impl = provider_registry.try_get(row.code)
    if impl is None:
        if require_impl:
            return None
        return ProviderRead(
            code=row.code,
            name=row.name,
            is_enabled=row.is_enabled,
            max_batch_size=0,
        )
    return ProviderRead(
        code=row.code,
        name=row.name,
        is_enabled=row.is_enabled,
        max_batch_size=impl.max_batch_size,
    )


def providers_to_read(
    rows: list[Provider] | tuple[Provider, ...],
    *,
    require_impl: bool,
) -> list[ProviderRead]:
    items: list[ProviderRead] = []
    for row in rows:
        read = provider_to_read(row, require_impl=require_impl)
        if read is not None:
            items.append(read)
    return items
