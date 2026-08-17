from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.pagination import Page
from app.deps import CurrentAdminDep, CurrentUserDep, SessionDep
from app.domains.auth.repositories import (
    EmailAlreadyExistsError,
    LastAdminError,
    UserRepository,
)
from app.domains.auth.schemas import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me/",
    summary="Текущий пользователь",
    description="Возвращает профиль пользователя, определённого по HTTP Basic Auth.",
)
async def get_me(current_user: CurrentUserDep) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get(
    "/",
    summary="Список пользователей",
    description="Доступно только admin.",
)
async def list_users(
    session: SessionDep,
    _admin: CurrentAdminDep,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Page[UserRead]:
    repository = UserRepository(session)
    users = await repository.list(limit=limit, offset=offset)
    total = await repository.count()
    return Page(
        total=total,
        limit=limit,
        offset=offset,
        items=[UserRead.model_validate(u) for u in users],
    )


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Создать пользователя",
    description="Доступно только admin.",
)
async def create_user(
    session: SessionDep,
    _admin: CurrentAdminDep,
    payload: UserCreate,
) -> UserRead:
    repository = UserRepository(session)
    try:
        user = await repository.create(payload)
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        ) from exc
    return UserRead.model_validate(user)


@router.get(
    "/{user_id}/",
    summary="Пользователь по ID",
    description="Доступно только admin.",
)
async def get_user(
    session: SessionDep,
    _admin: CurrentAdminDep,
    user_id: UUID,
) -> UserRead:
    repository = UserRepository(session)
    user = await repository.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(user)


@router.patch(
    "/{user_id}/",
    summary="Обновить пользователя",
    description="Частичное обновление. Нельзя снять роль/деактивировать последнего active admin.",
)
async def update_user(
    session: SessionDep,
    _admin: CurrentAdminDep,
    user_id: UUID,
    payload: UserUpdate,
) -> UserRead:
    if (
        payload.email is None
        and payload.password is None
        and payload.name is None
        and payload.role is None
        and payload.is_active is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one field must be set",
        )

    repository = UserRepository(session)
    try:
        user = await repository.update(user_id, payload)
    except LastAdminError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot demote or deactivate the last active admin",
        ) from exc
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        ) from exc

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(user)
