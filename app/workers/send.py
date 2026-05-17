"""Consume send tasks and submit message batches to providers."""

import asyncio
import json
import logging

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage
from pydantic import ValidationError

from app.db.base import utcnow
from app.db.session import async_session_factory
from app.domains.mailing.enums import MessagesBatchStatus
from app.domains.mailing.repositories import MessagesBatchRepository
from app.domains.mailing.services import MailingSendingService
from app.domains.providers.base.exceptions import (
    ProviderPermanentError,
    ProviderTemporaryError,
)
from app.domains.providers.base.provider import ProviderBatch, ProviderMessage
from app.domains.providers.registry import provider_registry
from app.messaging import topology
from app.messaging.rabbitmq import connect, setup_topology
from app.messaging.schemas import SendBatchTask


logger = logging.getLogger(__name__)

PREFETCH_COUNT = 10
RECONNECT_SLEEP_SECONDS = 5.0


def _decode_task(message: AbstractIncomingMessage) -> SendBatchTask:
    """Decode a queue message into a send task."""
    payload = json.loads(message.body.decode("utf-8"))
    return SendBatchTask.model_validate(payload)


async def _publish_retry(channel: AbstractChannel, task: SendBatchTask) -> None:
    """Publish a send task to the delayed retry queue."""
    exchange = await channel.get_exchange(topology.SEND_EXCHANGE)
    await exchange.publish(
        aio_pika.Message(
            body=task.model_dump_json().encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        ),
        routing_key=topology.SEND_RETRY_ROUTING_KEY,
    )


def _build_provider_batch(batch_messages: list) -> ProviderBatch:
    """Build provider input from queued domain messages."""
    return ProviderBatch(
        messages=[
            ProviderMessage(
                message_id=message.id,
                msisdn=message.msisdn,
                text=message.text,
                send_on=utcnow(),
            )
            for message in batch_messages
        ]
    )


async def send_task(task: SendBatchTask) -> None:
    """Send one queued batch through its provider and persist the result."""
    async with async_session_factory() as session:
        repository = MessagesBatchRepository(session)
        service = MailingSendingService(session)

        async with session.begin():
            batch = await repository.get_for_sending(task.batch_id)
            if batch is None:
                logger.warning("Send batch not found", extra={"task": str(task)})
                return

            if batch.status == MessagesBatchStatus.SUBMITTED:
                logger.info("Send batch already submitted", extra={"task": str(task)})
                return

            if batch.status != MessagesBatchStatus.QUEUED:
                logger.warning(
                    "Send batch has unexpected status",
                    extra={"task": str(task), "status": batch.status},
                )
                return

            provider = await provider_registry.get(task.provider_code)
            provider_batch = _build_provider_batch(batch.messages)

            try:
                response = await provider.send(provider_batch)
            except ProviderPermanentError:
                await service.mark_batch_as_failed(batch)
                logger.exception("Provider rejected send batch", extra={"task": str(task)})
                return

            if not response.status:
                await service.mark_batch_as_failed(batch)
                logger.error("Provider returned failed send response", extra={"task": str(task)})
                return

            response_message_ids = {item.message_id for item in response.messages}
            batch_message_ids = {message.id for message in batch.messages}
            if response_message_ids != batch_message_ids:
                raise ProviderTemporaryError("Provider response does not match batch messages")

            await service.mark_batch_as_submitted(batch, response)


async def handle_message(
    message: AbstractIncomingMessage, channel: AbstractChannel
) -> None:
    """Handle one RabbitMQ message from the send queue."""
    try:
        task = _decode_task(message)
    except (json.JSONDecodeError, ValidationError):
        logger.exception("Invalid send task payload")
        await message.ack()
        return

    try:
        await send_task(task)
    except ProviderTemporaryError:
        logger.exception("Temporary provider error", extra={"task": str(task)})
        await _publish_retry(channel, task)
        await message.ack()
        return
    except Exception:
        logger.exception("Failed to process send task", extra={"task": str(task)})
        await message.nack(requeue=True)
        return

    await message.ack()


async def consume() -> None:
    """Run the send consumer until the process is stopped."""
    while True:
        try:
            connection = await connect()
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=PREFETCH_COUNT)
                await setup_topology(channel)

                queue = await channel.get_queue(topology.SEND_QUEUE)
                await queue.consume(lambda message: handle_message(message, channel))
                logger.info("Send consumer started")
                await asyncio.Future()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Send consumer stopped unexpectedly")
            await asyncio.sleep(RECONNECT_SLEEP_SECONDS)


def main() -> None:
    """CLI entrypoint for the send consumer."""
    asyncio.run(consume())


if __name__ == "__main__":
    main()
