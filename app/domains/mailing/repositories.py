from collections.abc import Sequence
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.mailing.enums import MailingOutboxStatus, MessagesBatchStatus
from app.domains.mailing.models import (
    Mailing,
    MailingStatus,
    Message,
    MessagesBatch,
    MailingOutbox,
)
from app.domains.mailing.schemas import MailingCreate


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


class MailingOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def claim_for_publishing(
        self, *, limit: int = 100
    ) -> Sequence[MailingOutbox]:
        query = (
            select(MailingOutbox)
            .where(
                MailingOutbox.status == MailingOutboxStatus.PENDING
                or (
                    MailingOutbox.status == MailingOutboxStatus.FAILED
                    and MailingOutbox.next_retry_at < (datetime.now(timezone.utc))
                )
            )
            .order_by(MailingOutbox.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def mark_as_published(self, outbox: MailingOutbox) -> None:
        outbox.status = MailingOutboxStatus.PUBLISHED
        self.session.add(outbox)
        await self.session.flush()

    async def mark_as_failed(self, outbox: MailingOutbox) -> None:
        outbox.status = MailingOutboxStatus.FAILED
        outbox.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=1)
        self.session.add(outbox)
        await self.session.flush()
