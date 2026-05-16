from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.mailing.enums import MessageStatus, MessagesBatchStatus
from app.domains.mailing.models import Mailing, MailingStatus, Message, MessagesBatch
from app.domains.mailing.schemas import MailingCreate
from app.domains.providers.registry import provider_registry


class MailingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: MailingCreate, created_by_id: UUID) -> Mailing:
        mailing = Mailing(
            provider_code=payload.provider_code,
            created_by_id=created_by_id,
            updated_by_id=created_by_id,
        )
        self.session.add(mailing)
        await self.session.flush()

        provider = await provider_registry.get(payload.provider_code)

        for offset in range(0, len(payload.messages), provider.max_batch_size):
            chunk = payload.messages[offset : offset + provider.max_batch_size]
            batch = MessagesBatch(
                mailing_id=mailing.id,
                provider_code=payload.provider_code,
                messages_count=len(chunk),
            )
            self.session.add(batch)
            await self.session.flush()

            for item in chunk:
                message = Message(
                    msisdn=item.msisdn,
                    text=item.text,
                    batch_id=batch.id,
                    mailing_id=mailing.id,
                )
                self.session.add(message)

        await self.session.commit()
        await self.session.refresh(
            mailing,
            attribute_names=["messages", "batches", "created_by", "updated_by"],
        )

        return mailing

    async def get_by_id(self, mailing_id: UUID) -> Mailing | None:
        query = (
            select(Mailing)
            .options(
                selectinload(Mailing.messages),
                selectinload(Mailing.created_by),
                selectinload(Mailing.updated_by),
            )
            .where(Mailing.id == mailing_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

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

    async def update(self, mailing_id: UUID, *, updated_by_id: UUID) -> Mailing | None:
        mailing = await self.get_by_id(mailing_id)
        if mailing is None:
            return None

        mailing.updated_by_id = updated_by_id
        await self.session.commit()
        await self.session.refresh(
            mailing,
            attribute_names=["messages", "created_by", "updated_by"],
        )

    async def delete(self, mailing_id: UUID) -> bool:
        mailing = await self.get_by_id(mailing_id)
        if mailing is None:
            return False

        await self.session.delete(mailing)
        await self.session.flush()
        return True


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

    async def list_for_publishing(self, *, limit: int = 100) -> Sequence[MessagesBatch]:
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

    async def mark_as_queued(self, batch: MessagesBatch) -> None:
        """Mark a published batch and its messages as queued."""
        batch.status = MessagesBatchStatus.QUEUED
        for message in batch.messages:
            message.status = MessageStatus.QUEUED
        await self.session.flush()
