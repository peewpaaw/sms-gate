"""Domain services for mailing state transitions."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.mailing.enums import MessageStatus, MessagesBatchStatus
from app.domains.mailing.models import Mailing, MessagesBatch
from app.domains.mailing.schemas import SendBatchTask
from app.domains.providers.registry import provider_registry

from app.messaging.outbox.enums import OutboxEventType
from app.messaging.outbox.repository import OutboxRepository
from app.messaging.outbox.schemas import OutboxCreate


class MailingPublishingService:
    """Split mailing messages into provider-sized batches and publish to outbox"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.outbox_repository = OutboxRepository(session)


    async def publish_mailing(self, mailing: Mailing) -> None:
        """Create batches for a mailing and assign messages to them and publish to outbox"""
        if mailing.batches:
            return
        
        provider = await provider_registry.get(mailing.provider_code)
        messages = mailing.messages

        for offset in range(0, len(messages), provider.max_batch_size):
            chunk = messages[offset : offset + provider.max_batch_size]
            batch = MessagesBatch(
                status=MessagesBatchStatus.QUEUED,
                mailing_id=mailing.id,
                provider_code=mailing.provider_code,
                messages_count=len(chunk),
            )
            self.session.add(batch)
            await self.session.flush()

            outbox = await self.outbox_repository.create(
                OutboxCreate(
                    event_type=OutboxEventType.SEND_BATCH,
                    payload=SendBatchTask(
                        mailing_id=mailing.id,
                        batch_id=batch.id,
                        provider_code=mailing.provider_code,
                    ).model_dump(mode="json"),
                )
            )
            
            self.session.add(outbox)
            await self.session.flush()

            for item in chunk:
                item.batch_id = batch.id
                item.status = MessageStatus.QUEUED

        await self.session.flush()

            

