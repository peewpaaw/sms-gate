"""Domain services for mailing state transitions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.mailing.enums import MailingStatus, MessageStatus, MessagesBatchStatus
from app.domains.mailing.models import Mailing, MessagesBatch
from app.domains.providers.base.provider import ProviderSendResponse


class MailingQueueingService:
    """Apply queueing status transitions for mailings and batches."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def mark_batch_as_queued(self, batch: MessagesBatch) -> None:
        """Mark a published batch and its messages as queued."""
        batch.status = MessagesBatchStatus.QUEUED
        for message in batch.messages:
            message.status = MessageStatus.QUEUED
        await self.session.flush()

    async def mark_mailing_as_queued(self, mailing_id: UUID) -> bool:
        """Mark a mailing as queued when all its batches are queued."""
        has_not_queued_batches_query = (
            select(MessagesBatch.id)
            .where(MessagesBatch.mailing_id == mailing_id)
            .where(MessagesBatch.status != MessagesBatchStatus.QUEUED)
            .limit(1)
        )
        result = await self.session.execute(has_not_queued_batches_query)
        if result.scalar_one_or_none() is not None:
            return False

        mailing = await self.session.get(Mailing, mailing_id)
        if mailing is None or mailing.status == MailingStatus.QUEUED:
            return False

        mailing.status = MailingStatus.QUEUED
        await self.session.flush()
        return True


class MailingSendingService:
    """Apply sending result transitions for batches and messages."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def mark_batch_as_submitted(
        self, batch: MessagesBatch, response: ProviderSendResponse
    ) -> None:
        """Store provider ids and mark a sent batch as submitted."""
        provider_message_ids = {
            item.message_id: item.external_id for item in response.messages
        }

        batch.status = MessagesBatchStatus.SUBMITTED
        for message in batch.messages:
            message.provider_message_id = provider_message_ids.get(message.id)
            message.status = MessageStatus.SUBMITTED

        await self.session.flush()

    async def mark_batch_as_failed(self, batch: MessagesBatch) -> None:
        """Mark a batch and its queued messages as failed."""
        batch.status = MessagesBatchStatus.FAILED
        for message in batch.messages:
            if message.status == MessageStatus.QUEUED:
                message.status = MessageStatus.FAILED

        await self.session.flush()
