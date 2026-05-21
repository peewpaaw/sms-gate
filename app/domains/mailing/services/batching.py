"""Domain services for mailing state transitions."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.mailing.enums import MailingStatus, MessageStatus, MessagesBatchStatus
from app.domains.mailing.models import Mailing, MessagesBatch
from app.domains.mailing.repositories import MessagesBatchRepository
from app.domains.providers.registry import provider_registry


class MailingBatchingService:
    """Split mailing messages into provider-sized batches."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def batch_mailing(self, mailing: Mailing) -> None:
        """Create batches for a mailing and assign messages to them."""
        batch_repository = MessagesBatchRepository(self.session)
        await batch_repository.delete_by_mailing_id(mailing.id)

        provider = await provider_registry.get(mailing.provider_code)
        messages = mailing.messages

        for offset in range(0, len(messages), provider.max_batch_size):
            chunk = messages[offset : offset + provider.max_batch_size]
            batch = MessagesBatch(
                mailing_id=mailing.id,
                provider_code=mailing.provider_code,
                status=MessagesBatchStatus.CREATED,
                messages_count=len(chunk),
            )
            self.session.add(batch)
            await self.session.flush()

            for item in chunk:
                item.batch_id = batch.id
                item.status = MessageStatus.PREPARED

        await self.session.flush()

        mailing.status = MailingStatus.PREPARED
