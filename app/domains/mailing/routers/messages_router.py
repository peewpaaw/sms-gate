from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.deps import CurrentUserDep, SessionDep
from app.domains.mailing.exceptions import (
    MailingNotFoundError,
    MailingStatusUpdateForbiddenError,
    MessageNotFoundError,
    MessageStatusMutationForbiddenError,
)
from app.domains.mailing.repositories import MessageRepository
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
    repository = MessageRepository(session)
    try:
        message = await repository.create(
            mailing_id, payload, updated_by_id=current_user.id
        )
    except MailingNotFoundError:
        raise HTTPException(status_code=404, detail="Mailing not found") from None
    except MailingStatusUpdateForbiddenError:
        raise HTTPException(
            status_code=409,
            detail="Mailing can be updated only in created status",
        ) from None
    return MessageRead.model_validate(message)


@router.get(
    "/{message_id}",
    summary="Сообщение рассылки по ID",
)
async def get_message(
    session: SessionDep,
    _current_user: CurrentUserDep,
    mailing_id: UUID,
    message_id: UUID,
) -> MessageRead:
    repository = MessageRepository(session)
    message = await repository.get(mailing_id, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
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
    repository = MessageRepository(session)
    try:
        message = await repository.update(
            mailing_id, message_id, payload, updated_by_id=current_user.id
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
    return MessageRead.model_validate(message)


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
    repository = MessageRepository(session)
    try:
        await repository.delete(
            mailing_id, message_id, updated_by_id=current_user.id
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

    await session.commit()
