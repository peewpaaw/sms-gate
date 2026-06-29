from fastapi import APIRouter

from app.deps import CurrentUserDep
from app.domains.auth.schemas import UserRead

router = APIRouter(prefix="/me", tags=["auth"])


@router.get("/")
async def get_me(current_user: CurrentUserDep) -> UserRead:
    return UserRead.model_validate(current_user)
