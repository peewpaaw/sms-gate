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

    async def create(self, payload: MailingCreate) -> Mailing:
        mailing = Mailing(
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
        await self.session.refresh(mailing, attribute_names=["messages"])
        return mailing

    async def get_by_id(self, mailing_id: UUID) -> Mailing | None:
        query = (
            select(Mailing)
            .options(selectinload(Mailing.messages))
            .where(Mailing.id == mailing_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[Mailing]:
        query = (
            select(Mailing)
            .options(selectinload(Mailing.messages))
            .order_by(Mailing.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update(
        self, mailing_id: UUID, *, status: MailingStatus | None = None
    ) -> Mailing | None:
        mailing = await self.get_by_id(mailing_id)
        if mailing is None:
            return None

        if status is not None:
            mailing.status = status

        await self.session.flush()
        await self.session.refresh(mailing, attribute_names=["messages"])
        return mailing

    async def delete(self, mailing_id: UUID) -> bool:
        mailing = await self.get_by_id(mailing_id)
        if mailing is None:
            return False

        await self.session.delete(mailing)
        await self.session.flush()
        return True
