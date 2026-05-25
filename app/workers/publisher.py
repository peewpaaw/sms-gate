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

from app.messaging.outbox.repository import OutboxRepository
from app.messaging.rabbitmq import connect, setup_topology
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


async def _publish_send_batch(channel: AbstractChannel, outbox: Outbox) -> None:
    """Publish a single batch send task to the send queue."""
    await _publish(
        channel=channel,
        exchange_name=topology.SEND_EXCHANGE,
        routing_key=topology.SEND_BATCH_ROUTING_KEY,
        payload=outbox.payload,
    )


async def publish_once(channel: AbstractChannel) -> int:
    async with async_session_factory() as session:
        outbox_repository = OutboxRepository(session)
        async with session.begin():
            rows = await outbox_repository.claim_for_publishing(limit=PUBLISH_BATCH_SIZE)
            for row in rows:
                try:
                    await _publish_send_batch(channel, row)
                    await outbox_repository.mark_as_published(row)
                    await session.flush()
                except Exception:
                    await outbox_repository.mark_as_failed(row)
                    await session.flush()
                    raise
            return len(rows)


async def publish() -> None:
    """Run the publisher loop until the process is stopped."""
    connection = await connect()
    async with connection:
        channel = await connection.channel()
        await setup_topology(channel)

        while True:
            try:
                published_count = await publish_once(channel)
            except Exception as e:
                logger.exception("Failed to publish mailing batches: %e", e)
                await asyncio.sleep(ERROR_SLEEP_SECONDS)
                continue

            if published_count == 0:
                await asyncio.sleep(IDLE_SLEEP_SECONDS)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(publish())


if __name__ == "__main__":
    main()
