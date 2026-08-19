from uuid import UUID

from sqlalchemy import select

from app.domains.mailing.models import Message
from app.domains.mailing.repositories.base import SqlAlchemyRepository


class MessageRepository(SqlAlchemyRepository[Message]):
    model_type = Message

    async def get(self, mailing_id: UUID, message_id: UUID) -> Message | None:
        query = select(Message).where(
            Message.id == message_id,
            Message.mailing_id == mailing_id,
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_for_update(
        self, mailing_id: UUID, message_id: UUID
    ) -> Message | None:
        query = (
            select(Message)
            .where(
                Message.id == message_id,
                Message.mailing_id == mailing_id,
            )
            .with_for_update()
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()
