from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.mailing.models import (
    Mailing,
    MailingStatus,
    MessageStatus,
    MessagesBatch,
    MessagesBatchStatus,
)
from app.domains.mailing.repositories import MessagesBatchRepository
from app.domains.providers.base.provider import ProviderSendResponse
from app.messaging.outbox.enums import OutboxEventType
from app.messaging.outbox.repository import OutboxRepository
from app.messaging.outbox.schemas import OutboxCreate
from app.messaging.schemas import GetMessageStatusTask

_TERMINAL_BATCH_STATUSES = frozenset(
    {
        MessagesBatchStatus.SUBMITTED,
        MessagesBatchStatus.PARTIALLY_SUBMITTED,
        MessagesBatchStatus.FAILED,
        MessagesBatchStatus.COMPLETED,
        MessagesBatchStatus.PARTIALLY_FAILED,
    }
)
_SEND_DONE_BATCH_STATUSES = frozenset(
    {
        MessagesBatchStatus.SUBMITTED,
        MessagesBatchStatus.PARTIALLY_SUBMITTED,
        MessagesBatchStatus.FAILED,
    }
)
_CLAIMABLE_BATCH_STATUSES = frozenset(
    {
        MessagesBatchStatus.QUEUED,
        MessagesBatchStatus.SENDING,
    }
)


class MailingSendingService:
    """Apply sending result transitions for batches and messages."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._batch_repository = MessagesBatchRepository(session)
        self._outbox_repository = OutboxRepository(session)

    async def begin_send(self, batch_id: UUID) -> MessagesBatch | None:
        """Lock batch and mark SENDING if QUEUED. Recover in-flight SENDING.

        Returns None when batch is missing, terminal, or not claimable — caller should ack.
        """
        batch = await self._batch_repository.get_for_sending(batch_id)
        if batch is None:
            return None
        if batch.status in _TERMINAL_BATCH_STATUSES:
            return None
        if batch.status not in _CLAIMABLE_BATCH_STATUSES:
            return None
        if batch.status == MessagesBatchStatus.QUEUED:
            await self.mark_as_sending(batch)
        return batch

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

        if batch.status in _TERMINAL_BATCH_STATUSES:
            return True

        external_ids = {item.message_id: item.external_id for item in response.messages}
        batch_message_ids = {message.id for message in batch.messages}
        is_full_response = batch_message_ids <= set(external_ids)

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

            await self._outbox_repository.create(
                OutboxCreate(
                    event_type=OutboxEventType.CHECK_STATUS,
                    payload=GetMessageStatusTask(
                        message_id=message.id,
                        external_id=external_id,
                        provider_code=batch.provider_code,
                    ).model_dump(mode="json"),
                )
            )

        await self._session.flush()
        await self._maybe_mark_mailing_submitted(batch.mailing_id)
        return is_full_response
    
    async def _maybe_mark_mailing_submitted(self, mailing_id: UUID) -> None:
        """Close send-phase: SUBMITTED if any batch accepted, else FAILED."""
        mailing = await self._session.get(Mailing, mailing_id, with_for_update=True)
        if mailing is None or mailing.status != MailingStatus.QUEUED:
            return

        result = await self._session.execute(
            select(MessagesBatch.status).where(MessagesBatch.mailing_id == mailing_id)
        )
        statuses = list(result.scalars().all())
        if not statuses:
            return
        if not all(status in _SEND_DONE_BATCH_STATUSES for status in statuses):
            return

        if all(status == MessagesBatchStatus.FAILED for status in statuses):
            mailing.status = MailingStatus.FAILED
        else:
            mailing.status = MailingStatus.SUBMITTED
        await self._session.flush()

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
            if message.external_id is not None:
                continue
            if message.status == MessageStatus.SUBMITTED:
                continue
            message.status = MessageStatus.QUEUED

        await self._session.flush()

    async def mark_as_failed(self, batch_id: UUID) -> None:
        """Mark a batch and its non-submitted messages as failed."""
        batch = await self._batch_repository.get_by_id(batch_id)
        if batch is None:
            return

        mailing_id = batch.mailing_id
        batch.status = MessagesBatchStatus.FAILED
        for message in batch.messages:
            if message.external_id is not None:
                continue
            if message.status == MessageStatus.SUBMITTED:
                continue
            message.status = MessageStatus.FAILED

        await self._session.flush()
        await self._maybe_mark_mailing_submitted(mailing_id)
