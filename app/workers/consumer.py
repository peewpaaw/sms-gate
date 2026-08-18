"""Consume send tasks and submit message batches to providers."""

import asyncio
import json
import logging

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage
from pydantic import ValidationError

from app.db.session import async_session_factory
from app.domains.mailing.enums import MessagesBatchStatus
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


def _decode_task(message: AbstractIncomingMessage) -> SendBatchTask:
    """Decode a queue message into a send task."""
    payload = json.loads(message.body.decode("utf-8"))
    return SendBatchTask.model_validate(payload)


async def _publish_retry(channel: AbstractChannel, task: SendBatchTask) -> None:
    """Publish a send task to the delayed retry queue."""
    exchange = await channel.get_exchange(topology.MAILING_EXCHANGE)
    await exchange.publish(
        aio_pika.Message(
            body=task.model_dump_json().encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        ),
        routing_key=topology.SEND_BATCH_RETRY_ROUTING_KEY,
    )


def _build_provider_batch(batch_messages: list) -> ProviderBatch:
    """Build provider input from queued domain messages."""
    return ProviderBatch(
        messages=[
            ProviderMessage(
                message_id=message.id,
                msisdn=message.msisdn,
                text=message.text,
                send_on=message.send_on,
            )
            for message in batch_messages
        ]
    )


async def send_task(task: SendBatchTask) -> None:
    """Send one queued batch through its provider and persist the result."""
    logging.info("Sending task: %s", task)
    async with async_session_factory() as session:
        async with session.begin():
            service = MailingSendingService(session)
            batch = await service.claim_for_sending(task.batch_id)

            logger.info("claimed batch", extra={"task": str(task), "batch": batch})

            if batch is None:
                logger.warning("Batch not found", extra={"task": str(task)})
                return

            # Некорректный статус батча
            if batch.status != MessagesBatchStatus.QUEUED:
                logger.warning(
                    "Batch not in expected status: %s",
                    batch.status,
                    extra={"task": str(task)},
                )
                return

            logger.info(
                "marking batch as sending", extra={"task": str(task), "batch": batch}
            )
            await service.mark_as_sending(batch)

            provider_batch = _build_provider_batch(batch.messages)
            batch_id = batch.id

    # Все ок: обрабатываем батч (в статусе QUEUED -> SENDING)
    provider = await provider_registry.get(task.provider_code)

    try:
        logger.info("sending batch to provider", extra={"task": str(task)})
        response = await provider.send(provider_batch)
    except ProviderPermanentError:
        # Устанавливаем статус FAILED
        # return -> ack
        logger.info(
            "marking batch as failed", extra={"task": str(task), "batch": batch}
        )
        async with async_session_factory() as session:
            async with session.begin():
                await MailingSendingService(session).mark_as_failed(batch_id)
        logger.exception("Provider rejected send batch", extra={"task": str(task)})
        return
    except ProviderTemporaryError:
        # Возвращаем статус QUEUED
        # райзим ProviderTemporaryError -> уйдет в retry queue
        logger.info(
            "marking batch as failed", extra={"task": str(task), "batch": batch}
        )
        async with async_session_factory() as session:
            async with session.begin():
                await MailingSendingService(session).mark_as_queued(batch_id)
        logger.exception("Provider temporary error", extra={"task": str(task)})
        raise

    async with async_session_factory() as session:
        async with session.begin():

            service = MailingSendingService(session)
            logger.info(
                "processing provider response",
                extra={"task": str(task), "response": response},
            )

            if not response.status:
                await service.mark_as_failed(batch_id)
                logger.error(
                    "Provider returned failed send response", extra={"task": str(task)}
                )
                return

            is_full_response = await service.apply_send_response(batch_id, response)
            if not is_full_response:
                logger.error(
                    "Provider response does not match batch messages",
                    extra={"task": str(task)},
                )


async def handle_message(
    message: AbstractIncomingMessage, channel: AbstractChannel
) -> None:
    """Handle one RabbitMQ message from the send queue."""
    logging.info("Handling message: %s", message.body)
    try:
        task = _decode_task(message)
    except (json.JSONDecodeError, ValidationError):
        logger.exception("Invalid send task payload")
        await message.ack()
        return

    try:
        await send_task(task)
    except ProviderTemporaryError as e:
        logger.warning(
            "Task failed, will be retried", extra={"task": str(task), "error": e}
        )
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
    logging.info("Consumer-sender service has started")
    while True:
        try:
            connection = await connect()
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=PREFETCH_COUNT)
                await setup_topology(channel)

                queue = await channel.get_queue(topology.SEND_BATCH_QUEUE)
                await queue.consume(lambda message: handle_message(message, channel))
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
