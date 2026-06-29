from fastapi import APIRouter

from app.deps import CurrentUserDep
from app.domains.providers.registry import provider_registry
from app.domains.providers.schemas import ProviderListResponse

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get(
    "/",
    summary="Список провайдеров",
    description="Коды и метаданные провайдеров, доступных для создания рассылок.",
)
async def list_providers(_current_user: CurrentUserDep) -> ProviderListResponse:
    items = await provider_registry.list()
    return ProviderListResponse(items=items)
