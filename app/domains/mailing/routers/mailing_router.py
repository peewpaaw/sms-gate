from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.pagination import Page
from app.deps import SessionDep, CurrentUserDep
from app.domains.mailing.application.exceptions import (
    MailingBatchesNotEmptyError,
    MailingMessagesEmptyError,
    MailingNotFoundError,
    MailingStatusDeleteForbiddenError,
    MailingStatusPublishForbiddenError,
    MailingStatusUpdateForbiddenError,
)
from app.domains.mailing.application.mailing_service import MailingService
from app.domains.mailing.filters import MailingFilter
from app.domains.mailing.routers.messages_router import router as messages_router
from app.domains.mailing.schemas import (
    MailingCreate,
    MailingRead,
    MailingUpdate,
)
from app.domains.providers.exceptions import (
    ProviderDisabledError,
    ProviderNotFoundError,
    ProviderNotImplementedError,
)


router = APIRouter(prefix="/mailings", tags=["mailings"])
router.include_router(messages_router, prefix="/{mailing_id}/messages")


@router.get(
    "/",
    summary="Список рассылок",
    description="Пагинация, опциональный фильтр по статусу и поиск по name.",
)
async def get_mailings(
    session: SessionDep,
    _current_user: CurrentUserDep,
    filters: Annotated[MailingFilter, Depends()],
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> Page[MailingRead]:
    service = MailingService(session)
    mailings, total = await service.list(
        status=filters.status,
        search=filters.search,
        limit=limit,
        offset=offset,
    )
    return Page(
        total=total,
        limit=limit,
        offset=offset,
        items=[MailingRead.model_validate(mailing) for mailing in mailings],
    )


@router.post(
    "/",
    summary="Создать рассылку",
    description="Создаёт рассылку и сообщения получателей. Отправка — отдельным методом.",
)
async def create_mailing(
    session: SessionDep,
    current_user: CurrentUserDep,
    payload: MailingCreate,
) -> MailingRead:
    service = MailingService(session)
    try:
        mailing = await service.create(payload, created_by_id=current_user.id)
    except ProviderNotFoundError:
        raise HTTPException(status_code=422, detail="Unknown provider") from None
    except ProviderDisabledError:
        raise HTTPException(status_code=422, detail="Provider disabled") from None
    except ProviderNotImplementedError:
        raise HTTPException(
            status_code=422, detail="Provider is not configured on this server"
        ) from None
    result = MailingRead.model_validate(mailing)
    await session.commit()
    return result


@router.put(
    "/{mailing_id}",
    summary="Обновить рассылку",
    description=(
        "Обновляет provider_code. Если передан `messages` — полная замена списка; "
        "если поле отсутствует — сообщения не меняются. Доступно только в статусе created."
    ),
)
async def update_mailing(
    session: SessionDep,
    current_user: CurrentUserDep,
    mailing_id: UUID,
    payload: MailingUpdate,
) -> MailingRead:
    service = MailingService(session)
    try:
        mailing = await service.update(
            mailing_id, payload, updated_by_id=current_user.id
        )
    except MailingNotFoundError:
        raise HTTPException(status_code=404, detail="Mailing not found") from None
    except MailingStatusUpdateForbiddenError:
        raise HTTPException(
            status_code=409,
            detail="Mailing can be updated only in created status",
        ) from None
    except ProviderNotFoundError:
        raise HTTPException(status_code=422, detail="Unknown provider") from None
    except ProviderDisabledError:
        raise HTTPException(status_code=422, detail="Provider disabled") from None
    except ProviderNotImplementedError:
        raise HTTPException(
            status_code=422, detail="Provider is not configured on this server"
        ) from None
    result = MailingRead.model_validate(mailing)
    await session.commit()
    return result


@router.get(
    "/{mailing_id}",
    summary="Рассылка по ID",
)
async def get_mailing(
    session: SessionDep,
    mailing_id: UUID,
    _current_user: CurrentUserDep,
) -> MailingRead:
    service = MailingService(session)
    try:
        mailing = await service.get(mailing_id)
    except MailingNotFoundError:
        raise HTTPException(status_code=404, detail="Mailing not found") from None

    return MailingRead.model_validate(mailing)


@router.delete(
    "/{mailing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить рассылку",
)
async def delete_mailing(
    session: SessionDep,
    _current_user: CurrentUserDep,
    mailing_id: UUID,
) -> None:
    service = MailingService(session)
    try:
        await service.delete(mailing_id)
        await session.commit()
    except MailingNotFoundError:
        raise HTTPException(status_code=404, detail="Mailing not found") from None
    except MailingStatusDeleteForbiddenError:
        raise HTTPException(
            status_code=409,
            detail="Mailing can be deleted only in created status",
        ) from None


@router.post(
    "/{mailing_id}/send",
    summary="Отправить рассылку",
    description=(
        "Разбивает сообщения на батчи, переводит в очередь на отправку через outbox/publisher."
    ),
)
async def send_mailing(
    session: SessionDep,
    mailing_id: UUID,
    _current_user: CurrentUserDep,
) -> dict[str, str]:
    service = MailingService(session)
    try:
        await service.publish(mailing_id)
        await session.commit()
    except MailingNotFoundError:
        raise HTTPException(status_code=404, detail="Mailing not found") from None
    except MailingStatusPublishForbiddenError:
        raise HTTPException(
            status_code=409,
            detail="Mailing can be sent only in created status",
        ) from None
    except MailingBatchesNotEmptyError:
        raise HTTPException(
            status_code=409,
            detail="Mailing already batched",
        ) from None
    except MailingMessagesEmptyError:
        raise HTTPException(
            status_code=422,
            detail="Mailing has no messages",
        ) from None
    except ProviderNotFoundError:
        raise HTTPException(status_code=422, detail="Unknown provider") from None
    except ProviderDisabledError:
        raise HTTPException(status_code=422, detail="Provider disabled") from None
    except ProviderNotImplementedError:
        raise HTTPException(
            status_code=422,
            detail="Provider is not configured on this server",
        ) from None
    return {"message": "Mailing batched"}
