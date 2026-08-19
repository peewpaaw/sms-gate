from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domains.mailing.models import MessagesBatch, MessagesBatchStatus
from app.domains.mailing.repositories.base import SqlAlchemyRepository


class MessagesBatchRepository(SqlAlchemyRepository[MessagesBatch]):
    model_type = MessagesBatch

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
        result = await self._session.execute(query)
        return result.scalars().all()

    async def get_by_id(self, batch_id: UUID) -> MessagesBatch | None:
        query = (
            select(MessagesBatch)
            .options(selectinload(MessagesBatch.messages))
            .where(MessagesBatch.id == batch_id)
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_for_sending(self, batch_id: UUID) -> MessagesBatch | None:
        """Return one locked batch with messages for send processing."""
        query = (
            select(MessagesBatch)
            .options(selectinload(MessagesBatch.messages))
            .where(MessagesBatch.id == batch_id)
            .with_for_update()
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()
