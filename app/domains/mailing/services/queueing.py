"""Domain services for mailing state transitions."""

from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.mailing.enums import MailingStatus, MessageStatus, MessagesBatchStatus
from app.domains.mailing.models import Mailing, MessagesBatch


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

    async def claim_for_queueing(self, *, limit: int = 100) -> Sequence[MessagesBatch]:
        """Return created batches ready to be published by a worker.

        Rows are locked with SKIP LOCKED so multiple publisher processes can
        work concurrently without taking the same batch.
        """
        query = (
            select(MessagesBatch)
            .options(selectinload(MessagesBatch.messages))
            .where(MessagesBatch.status == MessagesBatchStatus.CREATED)
            .order_by(MessagesBatch.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(query)
        return result.scalars().all()