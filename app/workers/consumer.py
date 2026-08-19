"""Consume send tasks and submit message batches to providers."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage
from pydantic import ValidationError

from app.db.session import async_session_factory
from app.domains.mailing.application.sending_service import MailingSendingService
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
MAX_RETRY_COUNT = 5
RETRY_COUNT_HEADER = "x-retry-count"


def _decode_task(message: AbstractIncomingMessage) -> SendBatchTask:
    payload = json.loads(message.body.decode("utf-8"))
    return SendBatchTask.model_validate(payload)


def _retry_count(message: AbstractIncomingMessage) -> int:
    headers = message.headers or {}
    raw = headers.get(RETRY_COUNT_HEADER, 0)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


async def _publish_task(
    channel: AbstractChannel,
    task: SendBatchTask,
    *,
    routing_key: str,
    retry_count: int,
) -> None:
    exchange = await channel.get_exchange(topology.MAILING_EXCHANGE)
    await exchange.publish(
        aio_pika.Message(
            body=task.model_dump_json().encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers={RETRY_COUNT_HEADER: retry_count},
        ),
        routing_key=routing_key,
    )


def _build_provider_batch(batch: Any) -> ProviderBatch:
    return ProviderBatch(
        name=batch.mailing.name,
        messages=[
            ProviderMessage(
                message_id=message.id,
                msisdn=message.msisdn,
                text=message.text,
                send_on=message.send_on,
                external_id=message.external_id,
            )
            for message in batch.messages
        ],
    )


async def send_task(task: SendBatchTask) -> None:
    """Send one queued batch through its provider and persist the result."""
    logger.info("Sending task: %s", task)

    async with async_session_factory() as session:
        async with session.begin():
            service = MailingSendingService(session)
            batch = await service.begin_send(task.batch_id)
            if batch is None:
                logger.warning(
                    "Batch not claimable (missing or terminal)",
                    extra={"batch_id": str(task.batch_id)},
                )
                return
            provider_batch = _build_provider_batch(batch)
            batch_id = batch.id

    provider = await provider_registry.get(task.provider_code)

    try:
        logger.info("Sending batch to provider", extra={"batch_id": str(batch_id)})
        response = await provider.send(provider_batch)
    except ProviderPermanentError:
        logger.exception(
            "Provider rejected send batch",
            extra={"batch_id": str(batch_id)},
        )
        async with async_session_factory() as session:
            async with session.begin():
                await MailingSendingService(session).mark_as_failed(batch_id)
        return
    except ProviderTemporaryError:
        logger.exception(
            "Provider temporary error, requeue batch",
            extra={"batch_id": str(batch_id)},
        )
        async with async_session_factory() as session:
            async with session.begin():
                await MailingSendingService(session).mark_as_queued(batch_id)
        raise

    async with async_session_factory() as session:
        async with session.begin():
            service = MailingSendingService(session)
            if not response.status:
                await service.mark_as_failed(batch_id)
                logger.error(
                    "Provider returned failed send response",
                    extra={"batch_id": str(batch_id)},
                )
                return

            is_full_response = await service.apply_send_response(batch_id, response)
            if not is_full_response:
                logger.error(
                    "Provider response does not cover all batch messages",
                    extra={"batch_id": str(batch_id)},
                )


async def handle_message(
    message: AbstractIncomingMessage, channel: AbstractChannel
) -> None:
    """Handle one RabbitMQ message from the send queue."""
    logger.info("Handling message: %s", message.body)
    try:
        task = _decode_task(message)
    except (json.JSONDecodeError, ValidationError):
        logger.exception("Invalid send task payload")
        await message.ack()
        return

    try:
        await send_task(task)
    except ProviderTemporaryError as exc:
        retry_count = _retry_count(message) + 1
        if retry_count >= MAX_RETRY_COUNT:
            logger.warning(
                "Retry limit reached, moving to DLQ",
                extra={"task": str(task), "error": str(exc)},
            )
            await _publish_task(
                channel,
                task,
                routing_key=topology.SEND_BATCH_DEAD_ROUTING_KEY,
                retry_count=retry_count,
            )
        else:
            logger.warning(
                "Task failed, will be retried",
                extra={"task": str(task), "error": str(exc), "retry": retry_count},
            )
            await _publish_task(
                channel,
                task,
                routing_key=topology.SEND_BATCH_RETRY_ROUTING_KEY,
                retry_count=retry_count,
            )
        await message.ack()
        return
    except Exception as exc:
        retry_count = _retry_count(message) + 1
        if retry_count >= MAX_RETRY_COUNT:
            logger.exception(
                "Unexpected error, moving to DLQ",
                extra={"task": str(task), "error": str(exc)},
            )
            await _publish_task(
                channel,
                task,
                routing_key=topology.SEND_BATCH_DEAD_ROUTING_KEY,
                retry_count=retry_count,
            )
        else:
            logger.exception(
                "Unexpected error, will be retried",
                extra={"task": str(task), "error": str(exc), "retry": retry_count},
            )
            await _publish_task(
                channel,
                task,
                routing_key=topology.SEND_BATCH_RETRY_ROUTING_KEY,
                retry_count=retry_count,
            )
        await message.ack()
        return

    await message.ack()


async def consume() -> None:
    """Run the send consumer until the process is stopped."""
    logger.info("Consumer-sender service has started")
    while True:
        try:
            connection = await connect()
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=PREFETCH_COUNT)
                await setup_topology(channel)

                queue = await channel.get_queue(topology.SEND_BATCH_QUEUE)
                await queue.consume(lambda msg: handle_message(msg, channel))
                logger.info("Send consumer started")
                await asyncio.Future()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Send consumer stopped unexpectedly")
            await asyncio.sleep(RECONNECT_SLEEP_SECONDS)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(consume())


if __name__ == "__main__":
    main()
