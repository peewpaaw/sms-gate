from fastapi import APIRouter

from app.deps import CurrentUserDep
from app.domains.auth.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/me/",
    summary="Текущий пользователь",
    description="Возвращает профиль пользователя, определённого по `X-API-Key`.",
)
async def get_me(current_user: CurrentUserDep) -> UserRead:
    return UserRead.model_validate(current_user)
