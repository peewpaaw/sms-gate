from fastapi import APIRouter, HTTPException, Query, status

from app.deps import CurrentUserDep, SessionDep
from app.domains.providers.repositories import ProviderRepository
from app.domains.providers.schemas import (
    ProviderListResponse,
    ProviderRead,
    ProviderUpdate,
)
from app.domains.providers.services.catalog import provider_to_read, providers_to_read

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get(
    "/",
    summary="Список провайдеров",
    description="Коды и метаданные провайдеров, доступных для создания рассылок.",
)
async def list_providers(
    session: SessionDep,
    _current_user: CurrentUserDep,
    enabled_only: bool = Query(default=True),
) -> ProviderListResponse:
    repository = ProviderRepository(session)
    rows = await repository.list(enabled_only=enabled_only)
    items = providers_to_read(rows, require_impl=enabled_only)
    return ProviderListResponse(items=items)


@router.patch(
    "/{code}",
    summary="Обновить провайдер",
    description="Изменение отображаемого имени и флага доступности.",
)
async def update_provider(
    session: SessionDep,
    _current_user: CurrentUserDep,
    code: str,
    payload: ProviderUpdate,
) -> ProviderRead:
    if payload.name is None and payload.is_enabled is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one of name or is_enabled must be set",
        )

    repository = ProviderRepository(session)
    updated = await repository.update(
        code,
        name=payload.name,
        is_enabled=payload.is_enabled,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    read = provider_to_read(updated, require_impl=False)
    assert read is not None
    return read
