"""Domain services for mailing state transitions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.mailing.enums import MailingStatus, MessageStatus, MessagesBatchStatus
from app.domains.mailing.models import Mailing, MessagesBatch
from app.domains.mailing.repositories import MessagesBatchRepository
from app.domains.providers.base.provider import ProviderSendResponse
from app.domains.providers.registry import provider_registry


class MailingBatchingService:
    """Split mailing messages into provider-sized batches."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def batch_mailing(self, mailing: Mailing) -> None:
        """Create batches for a mailing and assign messages to them."""
        batch_repository = MessagesBatchRepository(self.session)
        await batch_repository.delete_by_mailing_id(mailing.id)

        provider = await provider_registry.get(mailing.provider_code)
        messages = mailing.messages

        for offset in range(0, len(messages), provider.max_batch_size):
            chunk = messages[offset : offset + provider.max_batch_size]
            batch = MessagesBatch(
                mailing_id=mailing.id,
                provider_code=mailing.provider_code,
                status=MessagesBatchStatus.CREATED,
                messages_count=len(chunk),
            )
            self.session.add(batch)
            await self.session.flush()

            for item in chunk:
                item.batch_id = batch.id
                item.status = MessageStatus.PREPARED

        await self.session.flush()

        mailing.status = MailingStatus.PREPARED


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

    async def apply_send_response(
        self, batch: MessagesBatch, response: ProviderSendResponse
    ) -> bool:
        """Store provider ids and mark messages that provider accepted.

        Returns True when provider returned a response for every message in the batch.
        Partial responses are persisted as well, because retrying accepted messages can
        duplicate SMS delivery.
        """
        external_ids = {item.message_id: item.external_id for item in response.messages}
        batch_message_ids = {message.id for message in batch.messages}
        is_full_response = set(external_ids) == batch_message_ids

        batch.status = (
            MessagesBatchStatus.SUBMITTED
            if is_full_response
            else MessagesBatchStatus.PARTIALLY_SUBMITTED
        )
        for message in batch.messages:
            external_id = external_ids.get(message.id)
            if external_id is None:
                message.status = MessageStatus.UNKNOWN
                continue

            message.external_id = external_id
            message.status = MessageStatus.SUBMITTED

        await self.session.flush()
        return is_full_response

    async def mark_batch_as_failed(self, batch: MessagesBatch) -> None:
        """Mark a batch and its queued messages as failed."""
        batch.status = MessagesBatchStatus.FAILED
        for message in batch.messages:
            if message.status == MessageStatus.QUEUED:
                message.status = MessageStatus.FAILED

        await self.session.flush()
