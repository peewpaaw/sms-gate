from collections.abc import Sequence
from uuid import UUID
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.mailing.enums import MailingStatus, MessageStatus, MessagesBatchStatus
from app.domains.mailing.models import (
    Mailing,
    MailingTemplate,
    Message,
    MessagesBatch,
)
from app.domains.mailing.exceptions import (
    MailingNotFoundError,
    MailingStatusDeleteForbiddenError,
    MailingStatusUpdateForbiddenError,
    MessageNotFoundError,
    MessageStatusMutationForbiddenError,
)
from app.domains.mailing.schemas import (
    MailingCreate,
    MailingTemplateCreate,
    MailingTemplateUpdate,
    MailingUpdate,
    MessageCreate,
    MessageUpdate,
)
from app.domains.providers.repositories import ProviderRepository
from app.domains.providers.validation import assert_provider_available_for_mailing


class MailingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: MailingCreate, created_by_id: UUID) -> Mailing:
        provider_repository = ProviderRepository(self.session)
        await assert_provider_available_for_mailing(
            provider_repository, payload.provider_code
        )

        mailing = Mailing(
            provider_code=payload.provider_code,
            created_by_id=created_by_id,
            updated_by_id=created_by_id,
        )
        self.session.add(mailing)
        await self.session.flush()

        for item in payload.messages:
            message = Message(
                msisdn=item.msisdn,
                text=item.text,
                send_on=item.send_on,
                mailing_id=mailing.id,
            )
            self.session.add(message)

        await self.session.commit()
        await self.session.refresh(mailing, attribute_names=["messages"])

        return mailing

    async def get_by_id(self, mailing_id: UUID) -> Mailing | None:
        query = (
            select(Mailing)
            .options(
                selectinload(Mailing.messages),
                selectinload(Mailing.batches),
                selectinload(Mailing.created_by),
                selectinload(Mailing.updated_by),
            )
            .where(Mailing.id == mailing_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, mailing_id: UUID) -> Mailing | None:
        query = (
            select(Mailing)
            .options(
                selectinload(Mailing.messages),
                selectinload(Mailing.batches),
                selectinload(Mailing.created_by),
                selectinload(Mailing.updated_by),
            )
            .where(Mailing.id == mailing_id)
            .with_for_update()
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update(
        self,
        mailing_id: UUID,
        payload: MailingUpdate,
        updated_by_id: UUID,
    ) -> Mailing:
        mailing = await self.get_by_id_for_update(mailing_id)
        if mailing is None:
            raise MailingNotFoundError
        if mailing.status != MailingStatus.CREATED:
            raise MailingStatusUpdateForbiddenError

        provider_repository = ProviderRepository(self.session)
        await assert_provider_available_for_mailing(
            provider_repository, payload.provider_code
        )

        mailing.provider_code = payload.provider_code
        mailing.updated_by_id = updated_by_id

        if payload.messages is not None:
            mailing.messages.clear()
            for item in payload.messages:
                mailing.messages.append(
                    Message(
                        msisdn=item.msisdn,
                        text=item.text,
                        send_on=item.send_on,
                        mailing_id=mailing.id,
                    )
                )

        await self.session.commit()
        updated = await self.get_by_id(mailing_id)
        assert updated is not None
        return updated

    async def list(
        self,
        *,
        status: MailingStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Mailing]:
        query = (
            select(Mailing)
            .options(
                selectinload(Mailing.messages),
                selectinload(Mailing.batches),
                selectinload(Mailing.created_by),
                selectinload(Mailing.updated_by),
            )
            .order_by(Mailing.created_at.desc())
        )
        if status is not None:
            query = query.where(Mailing.status == status)

        query = query.limit(limit).offset(offset)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count(self, *, status: MailingStatus | None = None) -> int:
        query = select(func.count()).select_from(Mailing)
        if status is not None:
            query = query.where(Mailing.status == status)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def delete(self, mailing_id: UUID) -> None:
        mailing = await self.get_by_id_for_update(mailing_id)
        if mailing is None:
            raise MailingNotFoundError
        if mailing.status != MailingStatus.CREATED:
            raise MailingStatusDeleteForbiddenError

        await self.session.delete(mailing)
        await self.session.flush()


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _require_mailing_created(self, mailing_id: UUID) -> Mailing:
        mailing = await MailingRepository(self.session).get_by_id_for_update(
            mailing_id
        )
        if mailing is None:
            raise MailingNotFoundError
        if mailing.status != MailingStatus.CREATED:
            raise MailingStatusUpdateForbiddenError
        return mailing

    async def get(self, mailing_id: UUID, message_id: UUID) -> Message | None:
        query = select(Message).where(
            Message.id == message_id,
            Message.mailing_id == mailing_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_for_update(
        self, mailing_id: UUID, message_id: UUID
    ) -> Message | None:
        query = (
            select(Message)
            .where(
                Message.id == message_id,
                Message.mailing_id == mailing_id,
            )
            .with_for_update()
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

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
            send_on=payload.send_on,
            mailing_id=mailing.id,
        )
        self.session.add(message)
        mailing.updated_by_id = updated_by_id
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def update(
        self,
        mailing_id: UUID,
        message_id: UUID,
        payload: MessageUpdate,
        updated_by_id: UUID,
    ) -> Message:
        mailing = await self._require_mailing_created(mailing_id)
        message = await self.get_for_update(mailing_id, message_id)
        if message is None:
            raise MessageNotFoundError
        if message.status != MessageStatus.CREATED:
            raise MessageStatusMutationForbiddenError

        message.msisdn = payload.msisdn
        message.text = payload.text
        message.send_on = payload.send_on
        mailing.updated_by_id = updated_by_id

        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def delete(
        self,
        mailing_id: UUID,
        message_id: UUID,
        updated_by_id: UUID,
    ) -> None:
        mailing = await self._require_mailing_created(mailing_id)
        message = await self.get_for_update(mailing_id, message_id)
        if message is None:
            raise MessageNotFoundError
        if message.status != MessageStatus.CREATED:
            raise MessageStatusMutationForbiddenError

        mailing.updated_by_id = updated_by_id
        await self.session.delete(message)
        await self.session.flush()


class MessagesBatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self, mailing_id: UUID, status: MessagesBatchStatus | None = None
    ) -> Sequence[MessagesBatch]:
        query = (
            select(MessagesBatch)
            .options(
                selectinload(MessagesBatch.mailing),
                selectinload(MessagesBatch.messages),
            )
            .where(MessagesBatch.mailing_id == mailing_id)
            .order_by(MessagesBatch.created_at.desc())
        )
        if status:
            query = query.where(MessagesBatch.status == status)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_for_sending(self, batch_id: UUID) -> MessagesBatch | None:
        """Return one locked batch with messages for send processing."""
        query = (
            select(MessagesBatch)
            .options(selectinload(MessagesBatch.messages))
            .where(MessagesBatch.id == batch_id)
            .with_for_update()
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def delete_by_mailing_id(self, mailing_id: UUID) -> None:
        query = (
            delete(MessagesBatch)
            .where(MessagesBatch.mailing_id == mailing_id)
            .execution_options(synchronize_session=False)
        )
        await self.session.execute(query)
        await self.session.flush()

    async def get_by_id(self, batch_id: UUID) -> MessagesBatch | None:
        query = (
            select(MessagesBatch)
            .options(selectinload(MessagesBatch.messages))
            .where(MessagesBatch.id == batch_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class MailingTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, payload: MailingTemplateCreate, created_by_id: UUID
    ) -> MailingTemplate:
        template = MailingTemplate(
            name=payload.name,
            text=payload.text,
            created_by_id=created_by_id,
            updated_by_id=created_by_id,
        )
        self.session.add(template)
        await self.session.commit()
        created = await self.get_by_id(template.id)
        assert created is not None
        return created

    async def get_by_id(self, template_id: UUID) -> MailingTemplate | None:
        query = (
            select(MailingTemplate)
            .options(
                selectinload(MailingTemplate.created_by),
                selectinload(MailingTemplate.updated_by),
            )
            .where(MailingTemplate.id == template_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[MailingTemplate]:
        query = (
            select(MailingTemplate)
            .options(
                selectinload(MailingTemplate.created_by),
                selectinload(MailingTemplate.updated_by),
            )
            .order_by(MailingTemplate.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def count(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(MailingTemplate)
        )
        return result.scalar_one()

    async def update(
        self,
        template_id: UUID,
        payload: MailingTemplateUpdate,
        updated_by_id: UUID,
    ) -> MailingTemplate | None:
        template = await self.get_by_id(template_id)
        if template is None:
            return None

        if payload.name is not None:
            template.name = payload.name
        if payload.text is not None:
            template.text = payload.text
        template.updated_by_id = updated_by_id

        await self.session.commit()
        updated = await self.get_by_id(template_id)
        assert updated is not None
        return updated

    async def delete(self, template_id: UUID) -> bool:
        template = await self.get_by_id(template_id)
        if template is None:
            return False

        await self.session.delete(template)
        await self.session.flush()
        return True
