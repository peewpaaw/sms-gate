from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.mailing.application.exceptions import (
    MailingBatchesNotEmptyError,
    MailingMessagesEmptyError,
    MailingNotFoundError,
    MailingStatusDeleteForbiddenError,
    MailingStatusPublishForbiddenError,
    MailingStatusUpdateForbiddenError,
)
from app.domains.mailing.models import (
    Mailing,
    MailingStatus,
    Message,
    MessageStatus,
    MessagesBatch,
    MessagesBatchStatus,
)
from app.domains.mailing.repositories import MailingRepository
from app.domains.mailing.schemas import MailingCreate, MailingUpdate, SendBatchTask
from app.domains.providers.exceptions import ProviderNotImplementedError
from app.domains.providers.registry import provider_registry
from app.domains.providers.repositories import ProviderRepository
from app.domains.providers.validation import assert_provider_available_for_mailing
from app.messaging.outbox.enums import OutboxEventType
from app.messaging.outbox.repository import OutboxRepository
from app.messaging.outbox.schemas import OutboxCreate


class MailingService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = MailingRepository(session)
        self._outbox_repo = OutboxRepository(session)

    async def list(
        self,
        *,
        status: MailingStatus | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Mailing], int]:
        mailings = list(
            await self._repo.list(
                status=status, search=search, limit=limit, offset=offset
            )
        )
        total = await self._repo.count(status=status, search=search)
        return mailings, total

    async def get(self, mailing_id: UUID) -> Mailing:
        mailing = await self._repo.get_by_id(mailing_id)
        if mailing is None:
            raise MailingNotFoundError
        return mailing

    async def create(self, payload: MailingCreate, created_by_id: UUID) -> Mailing:
        await assert_provider_available_for_mailing(
            ProviderRepository(self._session), payload.provider_code
        )

        mailing = Mailing(
            provider_code=payload.provider_code,
            name=payload.name,
            send_on=payload.send_on,
            created_by_id=created_by_id,
            updated_by_id=created_by_id,
            messages=[
                Message(
                    msisdn=item.msisdn,
                    text=item.text,
                )
                for item in payload.messages
            ],
        )
        self._repo.add(mailing)
        await self._session.flush()

        created = await self._repo.get_by_id(mailing.id)
        assert created is not None
        return created

    async def update(
        self,
        mailing_id: UUID,
        payload: MailingUpdate,
        updated_by_id: UUID,
    ) -> Mailing:
        mailing = await self._repo.get_for_update(mailing_id)
        if mailing is None:
            raise MailingNotFoundError
        if mailing.status != MailingStatus.CREATED:
            raise MailingStatusUpdateForbiddenError

        await assert_provider_available_for_mailing(
            ProviderRepository(self._session), payload.provider_code
        )

        mailing.provider_code = payload.provider_code
        mailing.name = payload.name
        mailing.send_on = payload.send_on
        mailing.updated_by_id = updated_by_id

        if payload.messages is not None:
            mailing.messages.clear()
            for item in payload.messages:
                mailing.messages.append(
                    Message(
                        msisdn=item.msisdn,
                        text=item.text,
                        mailing_id=mailing.id,
                    )
                )

        await self._session.flush()
        updated = await self._repo.get_by_id(mailing_id)
        assert updated is not None
        return updated

    async def delete(self, mailing_id: UUID) -> None:
        mailing = await self._repo.get_for_update(mailing_id)
        if mailing is None:
            raise MailingNotFoundError
        if mailing.status != MailingStatus.CREATED:
            raise MailingStatusDeleteForbiddenError

        await self._repo.delete(mailing)
        await self._session.flush()

    async def publish(self, mailing_id: UUID) -> None:
        """Lock mailing, create batches, write outbox rows, set QUEUED statuses.

        Does not commit — caller owns the transaction boundary.
        """
        mailing = await self._repo.get_for_update(mailing_id)
        if mailing is None:
            raise MailingNotFoundError

        if mailing.status != MailingStatus.CREATED:
            raise MailingStatusPublishForbiddenError

        if not mailing.messages:
            raise MailingMessagesEmptyError

        if mailing.batches:
            raise MailingBatchesNotEmptyError

        await assert_provider_available_for_mailing(
            ProviderRepository(self._session), mailing.provider_code
        )
        provider = await provider_registry.get(mailing.provider_code)
        if provider.max_batch_size < 1:
            raise ProviderNotImplementedError(mailing.provider_code)

        messages = sorted(
            mailing.messages,
            key=lambda message: (message.created_at, message.id),
        )

        for offset in range(0, len(messages), provider.max_batch_size):
            chunk = messages[offset : offset + provider.max_batch_size]
            batch = MessagesBatch(
                status=MessagesBatchStatus.QUEUED,
                mailing_id=mailing.id,
                provider_code=mailing.provider_code,
                messages_count=len(chunk),
            )
            self._session.add(batch)
            await self._session.flush()

            await self._outbox_repo.create(
                OutboxCreate(
                    event_type=OutboxEventType.SEND_BATCH,
                    payload=SendBatchTask(
                        mailing_id=mailing.id,
                        batch_id=batch.id,
                        provider_code=mailing.provider_code,
                    ).model_dump(mode="json"),
                )
            )

            for item in chunk:
                item.batch_id = batch.id
                item.status = MessageStatus.QUEUED

        mailing.status = MailingStatus.QUEUED
        await self._session.flush()
