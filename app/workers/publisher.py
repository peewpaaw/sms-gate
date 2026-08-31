"""Publish outbox rows to the send queue.

The database remains the source of truth. RabbitMQ carries lightweight send tasks.
Each outbox row is claimed, published, and marked in its own short transaction.
"""

from __future__ import annotations

import asyncio
import json
import logging

import aio_pika
from aio_pika.abc import AbstractChannel
from pydantic import ValidationError

from app.db.session import async_session_factory
from app.messaging import topology
from app.messaging.outbox.enums import OutboxEventType
from app.messaging.outbox.models import Outbox
from app.messaging.outbox.repository import OutboxRepository
from app.messaging.rabbitmq import connect, setup_topology
from app.messaging.schemas import GetMessageStatusTask, SendBatchTask

logger = logging.getLogger(__name__)

PUBLISH_BATCH_SIZE = 100
IDLE_SLEEP_SECONDS = 1.0
ERROR_SLEEP_SECONDS = 5.0
RECONNECT_SLEEP_SECONDS = 5.0


async def _publish_payload(
    channel: AbstractChannel,
    *,
    routing_key: str,
    payload: dict,
) -> None:
    """Publish a persistent JSON message and wait for broker confirm."""
    exchange = await channel.get_exchange(topology.MAILING_EXCHANGE)
    await exchange.publish(
        aio_pika.Message(
            body=json.dumps(payload, default=str).encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        ),
        routing_key=routing_key,
    )


def _routing_key_for(outbox: Outbox) -> str:
    if outbox.event_type == OutboxEventType.SEND_BATCH:
        return topology.SEND_BATCH_ROUTING_KEY
    if outbox.event_type == OutboxEventType.CHECK_STATUS:
        return topology.STATUS_ROUTING_KEY
    raise ValueError(f"Unsupported outbox event_type: {outbox.event_type}")


def _validate_payload(outbox: Outbox) -> dict:
    if outbox.event_type == OutboxEventType.SEND_BATCH:
        return SendBatchTask.model_validate(outbox.payload).model_dump(mode="json")
    if outbox.event_type == OutboxEventType.CHECK_STATUS:
        return GetMessageStatusTask.model_validate(outbox.payload).model_dump(
            mode="json"
        )
    raise ValueError(f"Unsupported outbox event_type: {outbox.event_type}")


async def publish_once(channel: AbstractChannel) -> int:
    """Claim and publish up to PUBLISH_BATCH_SIZE outbox rows, one TX each."""
    processed = 0
    while processed < PUBLISH_BATCH_SIZE:
        async with async_session_factory() as session:
            async with session.begin():
                repo = OutboxRepository(session)
                rows = await repo.claim_for_publishing(limit=1)
                if not rows:
                    break

                row = rows[0]
                try:
                    routing_key = _routing_key_for(row)
                    payload = _validate_payload(row)
                    await _publish_payload(
                        channel,
                        routing_key=routing_key,
                        payload=payload,
                    )
                    await repo.mark_as_published(row)
                    logger.info("Published outbox row %s", row.id)
                except (ValidationError, ValueError):
                    logger.exception(
                        "Invalid outbox payload, marking failed: %s", row.id
                    )
                    await repo.mark_as_failed(row)
                except Exception:
                    logger.exception("Failed to publish outbox row %s", row.id)
                    await repo.mark_as_failed(row)

                processed += 1

    return processed


async def publish() -> None:
    """Run the publisher loop until the process is stopped."""
    logger.info("Publisher service has started")
    while True:
        try:
            connection = await connect()
            async with connection:
                # publisher_confirms=True is the aio_pika Channel default
                channel = await connection.channel(publisher_confirms=True)
                await setup_topology(channel)
                logger.info("Publisher connected")

                while True:
                    try:
                        published_count = await publish_once(channel)
                    except Exception as exc:
                        logger.exception(
                            "Failed to publish mailing batches: %s", exc
                        )
                        await asyncio.sleep(ERROR_SLEEP_SECONDS)
                        continue

                    if published_count == 0:
                        await asyncio.sleep(IDLE_SLEEP_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Publisher stopped unexpectedly")
            await asyncio.sleep(RECONNECT_SLEEP_SECONDS)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(publish())


if __name__ == "__main__":
    main()
