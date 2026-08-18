from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.mailing.models import MessageStatus, MessagesBatch, MessagesBatchStatus
from app.domains.mailing.repositories import MessagesBatchRepository
from app.domains.providers.base.provider import ProviderSendResponse


class MailingSendingService:
    """Apply sending result transitions for batches and messages."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._batch_repository = MessagesBatchRepository(session)

    async def apply_send_response(
        self, batch_id: UUID, response: ProviderSendResponse
    ) -> bool:
        """Store provider ids and mark messages that provider accepted.

        Returns True when provider returned a response for every message in the batch.
        Partial responses are persisted as well, because retrying accepted messages can
        duplicate SMS delivery.
        """
        batch = await self._batch_repository.get_by_id(batch_id)
        if batch is None:
            return False

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

        await self._session.flush()
        return is_full_response

    async def claim_for_sending(self, batch_id: UUID) -> MessagesBatch | None:
        """Claim a batch for sending."""
        return await self._batch_repository.get_for_sending(batch_id)

    async def mark_as_sending(self, batch: MessagesBatch) -> None:
        """Mark a claimed batch as in-flight before calling the provider."""
        batch.status = MessagesBatchStatus.SENDING
        await self._session.flush()

    async def mark_as_queued(self, batch_id: UUID) -> None:
        """Mark a batch as queued after a temporary provider error."""
        batch = await self._batch_repository.get_by_id(batch_id)
        if batch is None:
            return

        batch.status = MessagesBatchStatus.QUEUED
        for message in batch.messages:
            message.status = MessageStatus.QUEUED

        await self._session.flush()

    async def mark_as_failed(self, batch_id: UUID) -> None:
        """Mark a batch and its queued messages as failed."""
        batch = await self._batch_repository.get_by_id(batch_id)
        if batch is None:
            return

        batch.status = MessagesBatchStatus.FAILED
        for message in batch.messages:
            if message.status == MessageStatus.QUEUED:
                message.status = MessageStatus.FAILED

        await self._session.flush()
