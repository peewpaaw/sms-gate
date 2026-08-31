from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.deps import CurrentUserDep, SessionDep, owner_scope
from app.domains.mailing.application.exceptions import (
    MailingNotFoundError,
    MailingStatusUpdateForbiddenError,
    MessageNotFoundError,
    MessageStatusMutationForbiddenError,
)
from app.domains.mailing.application.message_service import MessageService
from app.domains.mailing.schemas import MessageCreate, MessageRead, MessageUpdate

router = APIRouter(tags=["mailings"])


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить сообщение в рассылку",
    description="Доступно только пока рассылка в статусе created.",
)
async def create_message(
    session: SessionDep,
    current_user: CurrentUserDep,
    mailing_id: UUID,
    payload: MessageCreate,
) -> MessageRead:
    service = MessageService(session)
    try:
        message = await service.create(
            mailing_id,
            payload,
            updated_by_id=current_user.id,
            created_by_id=owner_scope(current_user),
        )
    except MailingNotFoundError:
        raise HTTPException(status_code=404, detail="Mailing not found") from None
    except MailingStatusUpdateForbiddenError:
        raise HTTPException(
            status_code=409,
            detail="Mailing can be updated only in created status",
        ) from None
    result = MessageRead.model_validate(message)
    await session.commit()
    return result


@router.get(
    "/{message_id}",
    summary="Сообщение рассылки по ID",
)
async def get_message(
    session: SessionDep,
    current_user: CurrentUserDep,
    mailing_id: UUID,
    message_id: UUID,
) -> MessageRead:
    service = MessageService(session)
    try:
        message = await service.get(
            mailing_id,
            message_id,
            created_by_id=owner_scope(current_user),
        )
    except MailingNotFoundError:
        raise HTTPException(status_code=404, detail="Mailing not found") from None
    except MessageNotFoundError:
        raise HTTPException(status_code=404, detail="Message not found") from None
    return MessageRead.model_validate(message)


@router.put(
    "/{message_id}",
    summary="Обновить сообщение рассылки",
    description=(
        "Полная замена полей сообщения. Рассылка и сообщение должны быть в статусе created."
    ),
)
async def update_message(
    session: SessionDep,
    current_user: CurrentUserDep,
    mailing_id: UUID,
    message_id: UUID,
    payload: MessageUpdate,
) -> MessageRead:
    service = MessageService(session)
    try:
        message = await service.update(
            mailing_id,
            message_id,
            payload,
            updated_by_id=current_user.id,
            created_by_id=owner_scope(current_user),
        )
    except MailingNotFoundError:
        raise HTTPException(status_code=404, detail="Mailing not found") from None
    except MessageNotFoundError:
        raise HTTPException(status_code=404, detail="Message not found") from None
    except MailingStatusUpdateForbiddenError:
        raise HTTPException(
            status_code=409,
            detail="Mailing can be updated only in created status",
        ) from None
    except MessageStatusMutationForbiddenError:
        raise HTTPException(
            status_code=409,
            detail="Message can be modified only in created status",
        ) from None
    result = MessageRead.model_validate(message)
    await session.commit()
    return result


@router.delete(
    "/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить сообщение из рассылки",
    description=(
        "Рассылка и сообщение должны быть в статусе created."
    ),
)
async def delete_message(
    session: SessionDep,
    current_user: CurrentUserDep,
    mailing_id: UUID,
    message_id: UUID,
) -> None:
    service = MessageService(session)
    try:
        await service.delete(
            mailing_id,
            message_id,
            updated_by_id=current_user.id,
            created_by_id=owner_scope(current_user),
        )
        await session.commit()
    except MailingNotFoundError:
        raise HTTPException(status_code=404, detail="Mailing not found") from None
    except MessageNotFoundError:
        raise HTTPException(status_code=404, detail="Message not found") from None
    except MailingStatusUpdateForbiddenError:
        raise HTTPException(
            status_code=409,
            detail="Mailing can be updated only in created status",
        ) from None
    except MessageStatusMutationForbiddenError:
        raise HTTPException(
            status_code=409,
            detail="Message can be modified only in created status",
        ) from None
