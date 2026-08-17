"""Domain services for mailing state transitions."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.mailing.enums import MailingStatus, MessageStatus, MessagesBatchStatus
from app.domains.mailing.exceptions import (
    MailingBatchesNotEmptyError,
    MailingMessagesEmptyError,
    MailingNotFoundError,
    MailingStatusPublishForbiddenError,
)
from app.domains.mailing.models import MessagesBatch
from app.domains.mailing.repositories import MailingRepository
from app.domains.mailing.schemas import SendBatchTask
from app.domains.providers.exceptions import ProviderNotImplementedError
from app.domains.providers.registry import provider_registry
from app.domains.providers.repositories import ProviderRepository
from app.domains.providers.validation import assert_provider_available_for_mailing
from app.messaging.outbox.enums import OutboxEventType
from app.messaging.outbox.repository import OutboxRepository
from app.messaging.outbox.schemas import OutboxCreate


class MailingPublishingService:
    """Split mailing messages into provider-sized batches and publish to outbox."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.mailing_repository = MailingRepository(session)
        self.outbox_repository = OutboxRepository(session)

    async def publish_mailing(self, mailing_id: UUID) -> None:
        """Lock mailing, create batches, write outbox rows, set QUEUED statuses.

        Does not commit — caller owns the transaction boundary.
        """
        mailing = await self.mailing_repository.get_by_id_for_update(mailing_id)
        if mailing is None:
            raise MailingNotFoundError

        if mailing.status != MailingStatus.CREATED:
            raise MailingStatusPublishForbiddenError

        if not mailing.messages:
            raise MailingMessagesEmptyError

        if mailing.batches:
            raise MailingBatchesNotEmptyError

        provider_repository = ProviderRepository(self.session)
        await assert_provider_available_for_mailing(
            provider_repository, mailing.provider_code
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
            self.session.add(batch)
            await self.session.flush()

            await self.outbox_repository.create(
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
        await self.session.flush()
