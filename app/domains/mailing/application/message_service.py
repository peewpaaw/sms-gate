from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.mailing.application.exceptions import (
    MailingNotFoundError,
    MailingStatusUpdateForbiddenError,
    MessageNotFoundError,
    MessageStatusMutationForbiddenError,
)
from app.domains.mailing.models import Mailing, MailingStatus, Message, MessageStatus
from app.domains.mailing.repositories import MailingRepository, MessageRepository
from app.domains.mailing.schemas import MessageCreate, MessageUpdate


class MessageService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = MessageRepository(session)
        self._mailing_repo = MailingRepository(session)

    async def _require_mailing_created(self, mailing_id: UUID) -> Mailing:
        mailing = await self._mailing_repo.get_for_update(mailing_id)
        if mailing is None:
            raise MailingNotFoundError
        if mailing.status != MailingStatus.CREATED:
            raise MailingStatusUpdateForbiddenError
        return mailing

    async def get(self, mailing_id: UUID, message_id: UUID) -> Message:
        message = await self._repo.get(mailing_id, message_id)
        if message is None:
            raise MessageNotFoundError
        return message

    async def create(
        self,
        mailing_id: UUID,
        payload: MessageCreate,
        updated_by_id: UUID,
    ) -> Message:
        mailing = await self._require_mailing_created(mailing_id)
        message = Message(
            msisdn=payload.msisdn,
            text=payload.text,
            mailing_id=mailing.id,
        )
        self._repo.add(message)
        mailing.updated_by_id = updated_by_id
        await self._session.flush()
        await self._session.refresh(message)
        return message

    async def update(
        self,
        mailing_id: UUID,
        message_id: UUID,
        payload: MessageUpdate,
        updated_by_id: UUID,
    ) -> Message:
        mailing = await self._require_mailing_created(mailing_id)
        message = await self._repo.get_for_update(mailing_id, message_id)
        if message is None:
            raise MessageNotFoundError
        if message.status != MessageStatus.CREATED:
            raise MessageStatusMutationForbiddenError

        message.msisdn = payload.msisdn
        message.text = payload.text
        mailing.updated_by_id = updated_by_id

        await self._session.flush()
        await self._session.refresh(message)
        return message

    async def delete(
        self,
        mailing_id: UUID,
        message_id: UUID,
        updated_by_id: UUID,
    ) -> None:
        mailing = await self._require_mailing_created(mailing_id)
        message = await self._repo.get_for_update(mailing_id, message_id)
        if message is None:
            raise MessageNotFoundError
        if message.status != MessageStatus.CREATED:
            raise MessageStatusMutationForbiddenError

        mailing.updated_by_id = updated_by_id
        await self._repo.delete(message)
        await self._session.flush()
