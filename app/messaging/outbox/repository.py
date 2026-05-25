

from datetime import datetime, timedelta, timezone
from typing import Sequence
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.messaging.outbox.enums import OutboxStatus
from app.messaging.outbox.models import Outbox
from app.messaging.outbox.schemas import OutboxCreate

# in seconds for next_retry_at
RETRY_DELAY = 60 


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: OutboxCreate) -> Outbox:
        outbox = Outbox(
            status=OutboxStatus.PENDING,
            event_type=payload.event_type,
            payload=payload.payload,
        )
        self.session.add(outbox)
        await self.session.flush()
        return outbox

    async def claim_for_publishing(self, *, limit: int = 100) -> Sequence[Outbox]:
        query = (
            select(Outbox)
            .where(
                or_(
                    Outbox.status == OutboxStatus.PENDING,
                    and_(
                        Outbox.status == OutboxStatus.FAILED,
                        Outbox.next_retry_at <= datetime.now(timezone.utc),
                    ),
                )
            )
            .order_by(Outbox.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def mark_as_published(self, outbox: Outbox) -> None:
        outbox.status = OutboxStatus.PUBLISHED
        outbox.published_at = datetime.now(timezone.utc)
        outbox.attempts += 1
        self.session.add(outbox)
        await self.session.flush()
    
    async def mark_as_failed(self, outbox: Outbox) -> None:
        outbox.status = OutboxStatus.FAILED
        outbox.attempts += 1
        outbox.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=RETRY_DELAY)
        self.session.add(outbox)
        await self.session.flush()