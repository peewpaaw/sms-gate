"""Domain services for mailing state transitions."""

from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.mailing.enums import MessageStatus, MessagesBatchStatus
from app.domains.mailing.models import MessagesBatch
from app.domains.providers.base.provider import ProviderSendResponse


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

        if is_full_response:
            batch.status = MessagesBatchStatus.SUBMITTED
        elif external_ids:
            batch.status = MessagesBatchStatus.PARTIALLY_SUBMITTED
        else:
            batch.status = MessagesBatchStatus.FAILED

        for message in batch.messages:
            external_id = external_ids.get(message.id)
            if external_id is None:
                message.status = MessageStatus.FAILED
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

    async def claim_for_sending(self, batch_id: UUID) -> MessagesBatch | None:
        """Claim a batch for sending."""
        query = (
            select(MessagesBatch)
            .options(selectinload(MessagesBatch.messages))
            .where(MessagesBatch.id == batch_id)
            .with_for_update()
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
