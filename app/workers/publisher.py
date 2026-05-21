"""Publish created message batches to the send queue.

The database remains the source of truth for mailings, batches, and messages.
RabbitMQ only carries lightweight send tasks that point consumers to a batch.
"""

import asyncio
import json
import logging

import aio_pika
from aio_pika.abc import AbstractChannel

from app.db.session import async_session_factory
from app.domains.mailing.repositories import MessagesBatchRepository
from app.domains.mailing.services.queueing import MailingQueueingService
from app.messaging.rabbitmq import connect, setup_topology
from app.messaging.schemas import SendBatchTask
from app.messaging import topology


logger = logging.getLogger(__name__)

PUBLISH_BATCH_SIZE = 100
IDLE_SLEEP_SECONDS = 1.0
ERROR_SLEEP_SECONDS = 5.0


async def _publish(
    channel: AbstractChannel,
    exchange_name: str,
    routing_key: str,
    payload: dict,
) -> None:
    """Publish a persistent JSON message to a RabbitMQ exchange."""
    exchange = await channel.get_exchange(exchange_name)
    await exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload, default=str).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        ),
        routing_key=routing_key,
    )


async def _publish_send_batch(channel: AbstractChannel, task: SendBatchTask) -> None:
    """Publish a single batch send task to the send queue."""
    await _publish(
        channel=channel,
        exchange_name=topology.SEND_EXCHANGE,
        routing_key=topology.SEND_BATCH_ROUTING_KEY,
        payload=task.model_dump(mode="json"),
    )


async def publish_send_batch(task: SendBatchTask) -> None:
    """Publish one send task using a short-lived RabbitMQ connection."""
    connection = await connect()
    async with connection:
        channel = await connection.channel()
        await setup_topology(channel)
        try:
            await _publish_send_batch(channel, task)
        except OSError:
            logger.exception("Failed to publish send mailing task", extra={"task": str(task)})
            raise


async def publish_once(channel: AbstractChannel) -> int:
    """Publish one locked page of created batches and mark them as queued.

    The status update happens only after a successful publish. If the process
    dies after publishing but before commit, a duplicate task can be published
    later, so the consumer must be idempotent.
    """
    async with async_session_factory() as session:
        service = MailingQueueingService(session)
        async with session.begin():
            batches = await service.claim_for_queueing(limit=PUBLISH_BATCH_SIZE)
            mailing_ids = set()

            for batch in batches:
                task = SendBatchTask(
                    mailing_id=batch.mailing_id,
                    batch_id=batch.id,
                    provider_code=batch.provider_code,
                )
                await _publish_send_batch(channel, task)
                await service.mark_batch_as_queued(batch)
                mailing_ids.add(batch.mailing_id)

            for mailing_id in mailing_ids:
                await service.mark_mailing_as_queued(mailing_id)

            return len(batches)


async def publish() -> None:
    """Run the publisher loop until the process is stopped."""
    connection = await connect()
    async with connection:
        channel = await connection.channel()
        await setup_topology(channel)

        while True:
            try:
                published_count = await publish_once(channel)
            except Exception:
                logger.exception("Failed to publish mailing batches")
                await asyncio.sleep(ERROR_SLEEP_SECONDS)
                continue

            if published_count == 0:
                await asyncio.sleep(IDLE_SLEEP_SECONDS)


def main() -> None:
    asyncio.run(publish())


if __name__ == "__main__":
    main()