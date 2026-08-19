from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.mailing.models import (
    Message,
    MessageStatus,
    MessagesBatch,
    MessagesBatchStatus,
)
from app.domains.providers.base.provider import (
    ProviderOneMessageStatusResponse,
    ProviderStatusResponse,
)

TERMINAL_MESSAGE_STATUSES = frozenset(
    {
        MessageStatus.DELIVERED,
        MessageStatus.UNDELIVERED,
        MessageStatus.FAILED,
    }
)

_SUCCESS_TERMINAL = frozenset({MessageStatus.DELIVERED})
_FAILURE_TERMINAL = frozenset(
    {MessageStatus.FAILED, MessageStatus.UNDELIVERED}
)


class MessageStatusService:
    """Apply provider status polls to messages with monotonic transitions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def apply_status_response(
        self,
        message_id: UUID,
        response: ProviderStatusResponse,
    ) -> MessageStatus | None:
        """Update message from provider status response.

        Returns the message status after apply, or None if message is missing /
        has no external_id. Raises StatusMatchError when response cannot be matched.
        """
        message = await self._get_message_for_update(message_id)
        if message is None or message.external_id is None:
            return None

        if message.status in TERMINAL_MESSAGE_STATUSES:
            return message.status

        item = self._match_status_item(message, response.messages_status)
        if item is None:
            raise StatusMatchError(
                f"No status item matched message {message_id}"
            )

        new_status = self._next_status(message.status, item.status)
        if new_status != message.status:
            message.status = new_status
            await self._session.flush()

        if message.batch_id is not None:
            await self._maybe_complete_batch(message.batch_id)

        return message.status

    async def _get_message_for_update(self, message_id: UUID) -> Message | None:
        query = (
            select(Message)
            .where(Message.id == message_id)
            .with_for_update()
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    def _match_status_item(
        self,
        message: Message,
        items: list[ProviderOneMessageStatusResponse],
    ) -> ProviderOneMessageStatusResponse | None:
        for item in items:
            if item.message_id is not None and item.message_id == message.id:
                return item

        normalized_msisdn = _normalize_msisdn(message.msisdn)
        for item in items:
            if item.msisdn is None:
                continue
            if _normalize_msisdn(item.msisdn) == normalized_msisdn:
                return item

        # Fake/dev: single anonymous item applies to the polled message.
        if len(items) == 1 and items[0].message_id is None and items[0].msisdn is None:
            return items[0]

        return None

    def _next_status(
        self, current: MessageStatus, incoming: MessageStatus
    ) -> MessageStatus:
        if current in TERMINAL_MESSAGE_STATUSES:
            return current
        if current in {MessageStatus.SUBMITTED, MessageStatus.UNKNOWN}:
            return incoming
        # CREATED / QUEUED should not be polled; keep as-is.
        return current

    async def _maybe_complete_batch(self, batch_id: UUID) -> None:
        batch = await self._session.get(
            MessagesBatch, batch_id, with_for_update=True
        )
        if batch is None:
            return

        result = await self._session.execute(
            select(Message).where(Message.batch_id == batch_id)
        )
        messages = list(result.scalars().all())
        if not messages:
            return
        if not all(m.status in TERMINAL_MESSAGE_STATUSES for m in messages):
            return

        statuses = {m.status for m in messages}
        if statuses <= _SUCCESS_TERMINAL:
            batch.status = MessagesBatchStatus.COMPLETED
        elif statuses <= _FAILURE_TERMINAL:
            batch.status = MessagesBatchStatus.FAILED
        else:
            batch.status = MessagesBatchStatus.PARTIALLY_FAILED

        await self._session.flush()


class StatusMatchError(Exception):
    """Provider status response did not contain a matching message entry."""


class StatusNotReady(Exception):
    """Message status is still non-terminal; poll again later."""


def _normalize_msisdn(value: str) -> str:
    return value.replace(" ", "").replace("+", "")
