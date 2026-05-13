from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domains.mailing.models import Mailing, MailingStatus, Message
from app.domains.mailing.schemas import MailingCreate


class MailingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: MailingCreate, created_by_id: UUID) -> Mailing:
        mailing = Mailing(
            created_by_id=created_by_id,
            updated_by_id=created_by_id,
            messages=[
                Message(
                    msisdn=message.msisdn,
                    text=message.text,
                )
                for message in payload.messages
            ]
        )
        self.session.add(mailing)
        await self.session.flush()
        await self.session.refresh(
            mailing,
            attribute_names=["messages", "created_by", "updated_by"],
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

    async def update(
        self, mailing_id: UUID, *, updated_by_id: UUID
    ) -> Mailing | None:
        mailing = await self.get_by_id(mailing_id)
        if mailing is None:
            return None

        mailing.updated_by_id = updated_by_id
        await self.session.flush()
        await self.session.refresh(
            mailing,
            attribute_names=["messages", "created_by", "updated_by"],
        )
        return mailing

    async def delete(self, mailing_id: UUID) -> bool:
        mailing = await self.get_by_id(mailing_id)
        if mailing is None:
            return False

        await self.session.delete(mailing)
        await self.session.flush()
        return True
