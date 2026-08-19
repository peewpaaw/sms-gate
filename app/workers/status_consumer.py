"""Consume status-check tasks and poll providers via get_status."""

from __future__ import annotations

import asyncio
import json
import logging

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage
from pydantic import ValidationError

from app.db.session import async_session_factory
from app.domains.mailing.application.status_service import (
    TERMINAL_MESSAGE_STATUSES,
    MessageStatusService,
    StatusMatchError,
    StatusNotReady,
)
from app.domains.mailing.models import Message
from app.domains.providers.base.exceptions import (
    ProviderPermanentError,
    ProviderTemporaryError,
)
from app.domains.providers.registry import provider_registry
from app.messaging import topology
from app.messaging.rabbitmq import connect, setup_topology
from app.messaging.schemas import GetMessageStatusTask

logger = logging.getLogger(__name__)

PREFETCH_COUNT = 10
RECONNECT_SLEEP_SECONDS = 5.0
MAX_RETRY_COUNT = 5
MAX_POLL_COUNT = 60
RETRY_COUNT_HEADER = "x-retry-count"
POLL_COUNT_HEADER = "x-poll-count"


def _decode_task(message: AbstractIncomingMessage) -> GetMessageStatusTask:
    payload = json.loads(message.body.decode("utf-8"))
    return GetMessageStatusTask.model_validate(payload)


def _header_int(message: AbstractIncomingMessage, name: str) -> int:
    headers = message.headers or {}
    raw = headers.get(name, 0)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


async def _publish_task(
    channel: AbstractChannel,
    task: GetMessageStatusTask,
    *,
    routing_key: str,
    retry_count: int,
    poll_count: int,
) -> None:
    exchange = await channel.get_exchange(topology.MAILING_EXCHANGE)
    await exchange.publish(
        aio_pika.Message(
            body=task.model_dump_json().encode("utf-8"),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers={
                RETRY_COUNT_HEADER: retry_count,
                POLL_COUNT_HEADER: poll_count,
            },
        ),
        routing_key=routing_key,
    )


async def check_status(task: GetMessageStatusTask) -> None:
    """Poll provider status for one message and persist the result."""
    logger.info("Checking status: %s", task)

    async with async_session_factory() as session:
        async with session.begin():
            message = await session.get(Message, task.message_id)
            if message is None:
                logger.warning(
                    "Message not found for status check",
                    extra={"message_id": str(task.message_id)},
                )
                return
            if message.external_id is None:
                logger.warning(
                    "Message has no external_id",
                    extra={"message_id": str(task.message_id)},
                )
                return
            if message.status in TERMINAL_MESSAGE_STATUSES:
                return

    provider = await provider_registry.get(task.provider_code)

    try:
        response = await provider.get_status(task.external_id)
    except ProviderPermanentError:
        logger.exception(
            "Provider permanently failed status check",
            extra={"message_id": str(task.message_id)},
        )
        return
    except ProviderTemporaryError:
        logger.exception(
            "Provider temporary error on status check",
            extra={"message_id": str(task.message_id)},
        )
        raise

    async with async_session_factory() as session:
        async with session.begin():
            service = MessageStatusService(session)
            try:
                status = await service.apply_status_response(
                    task.message_id, response
                )
            except StatusMatchError:
                logger.exception(
                    "Status response did not match message",
                    extra={"message_id": str(task.message_id)},
                )
                raise StatusNotReady from None

            if status is None:
                return
            if status not in TERMINAL_MESSAGE_STATUSES:
                raise StatusNotReady(
                    f"Message {task.message_id} still {status.value}"
                )


async def handle_message(
    message: AbstractIncomingMessage, channel: AbstractChannel
) -> None:
    logger.info("Handling status message: %s", message.body)
    try:
        task = _decode_task(message)
    except (json.JSONDecodeError, ValidationError):
        logger.exception("Invalid status task payload")
        await message.ack()
        return

    try:
        await check_status(task)
    except StatusNotReady as exc:
        poll_count = _header_int(message, POLL_COUNT_HEADER) + 1
        if poll_count >= MAX_POLL_COUNT:
            logger.warning(
                "Poll limit reached, moving to DLQ",
                extra={"task": str(task), "error": str(exc)},
            )
            await _publish_task(
                channel,
                task,
                routing_key=topology.STATUS_DEAD_ROUTING_KEY,
                retry_count=_header_int(message, RETRY_COUNT_HEADER),
                poll_count=poll_count,
            )
        else:
            logger.info(
                "Status not ready, will poll again",
                extra={"task": str(task), "poll": poll_count},
            )
            await _publish_task(
                channel,
                task,
                routing_key=topology.STATUS_RETRY_ROUTING_KEY,
                retry_count=_header_int(message, RETRY_COUNT_HEADER),
                poll_count=poll_count,
            )
        await message.ack()
        return
    except ProviderTemporaryError as exc:
        retry_count = _header_int(message, RETRY_COUNT_HEADER) + 1
        if retry_count >= MAX_RETRY_COUNT:
            logger.warning(
                "Retry limit reached, moving to DLQ",
                extra={"task": str(task), "error": str(exc)},
            )
            await _publish_task(
                channel,
                task,
                routing_key=topology.STATUS_DEAD_ROUTING_KEY,
                retry_count=retry_count,
                poll_count=_header_int(message, POLL_COUNT_HEADER),
            )
        else:
            logger.warning(
                "Status task failed, will be retried",
                extra={"task": str(task), "error": str(exc), "retry": retry_count},
            )
            await _publish_task(
                channel,
                task,
                routing_key=topology.STATUS_RETRY_ROUTING_KEY,
                retry_count=retry_count,
                poll_count=_header_int(message, POLL_COUNT_HEADER),
            )
        await message.ack()
        return
    except Exception as exc:
        retry_count = _header_int(message, RETRY_COUNT_HEADER) + 1
        if retry_count >= MAX_RETRY_COUNT:
            logger.exception(
                "Unexpected error, moving to DLQ",
                extra={"task": str(task), "error": str(exc)},
            )
            await _publish_task(
                channel,
                task,
                routing_key=topology.STATUS_DEAD_ROUTING_KEY,
                retry_count=retry_count,
                poll_count=_header_int(message, POLL_COUNT_HEADER),
            )
        else:
            logger.exception(
                "Unexpected error, will be retried",
                extra={"task": str(task), "error": str(exc), "retry": retry_count},
            )
            await _publish_task(
                channel,
                task,
                routing_key=topology.STATUS_RETRY_ROUTING_KEY,
                retry_count=retry_count,
                poll_count=_header_int(message, POLL_COUNT_HEADER),
            )
        await message.ack()
        return

    await message.ack()


async def consume() -> None:
    logger.info("Status consumer service has started")
    while True:
        try:
            connection = await connect()
            async with connection:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=PREFETCH_COUNT)
                await setup_topology(channel)

                queue = await channel.get_queue(topology.STATUS_QUEUE)
                await queue.consume(lambda msg: handle_message(msg, channel))
                logger.info("Status consumer started")
                await asyncio.Future()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Status consumer stopped unexpectedly")
            await asyncio.sleep(RECONNECT_SLEEP_SECONDS)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(consume())


if __name__ == "__main__":
    main()
