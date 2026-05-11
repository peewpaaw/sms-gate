import asyncio
import hashlib
import json
import logging

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import async_session_factory
from app.messaging import topology
from app.messaging.publisher import publish_status_check
from app.messaging.rabbitmq import connect, setup_topology
from app.messaging.schemas import SendBatchTask, StatusCheckTask
from app.models.enums import (
    MailingStatus,
    ProviderDispatchStatus,
    SmsBatchStatus,
    SmsMessageStatus,
)
from app.models.mailing import Mailing
from app.models.provider_dispatch import ProviderDispatch
from app.models.sms_batch import SmsBatch
from app.providers.base import (
    ProviderBatch,
    ProviderMessage,
    ProviderPermanentError,
    ProviderTemporaryError,
)
from app.providers.registry import provider_registry

logger = logging.getLogger(__name__)
MAX_RETRIES = 3


def _request_hash(payload: dict) -> str:
    serialized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def handle_send_task(task: SendBatchTask) -> None:
    async with async_session_factory() as session:
        batch = await session.scalar(
            select(SmsBatch)
            .where(SmsBatch.id == task.batch_id)
            .options(selectinload(SmsBatch.messages))
        )
        if batch is None:
            logger.warning("send_batch_not_found", extra={"batch_id": str(task.batch_id)})
            return

        if all(message.provider_message_id for message in batch.messages):
            logger.info("send_batch_already_submitted", extra={"batch_id": str(batch.id)})
            return

        adapter = provider_registry.get(task.provider_code)
        batch.status = SmsBatchStatus.SENDING
        batch.attempt_count += 1
        for message in batch.messages:
            if message.provider_message_id is None:
                message.status = SmsMessageStatus.SENDING

        provider_batch = ProviderBatch(
            provider_code=task.provider_code,
            batch_id=str(batch.id),
            sender=batch.messages[0].sender if batch.messages else "",
            messages=[
                ProviderMessage(
                    message_id=str(message.id),
                    custom_id=message.provider_custom_id,
                    msisdn=message.msisdn,
                    text=message.text,
                    sender=message.sender,
                )
                for message in batch.messages
                if message.provider_message_id is None
            ],
        )
        dispatch = ProviderDispatch(
            batch_id=batch.id,
            provider_code=task.provider_code,
            status=ProviderDispatchStatus.SENT_TO_PROVIDER,
            request_hash=_request_hash(
                {"batch": provider_batch.batch_id, "messages": provider_batch.messages}
            ),
            retry_count=max(batch.attempt_count - 1, 0),
        )
        session.add(dispatch)

        try:
            result = await adapter.send_batch(provider_batch)
        except ProviderTemporaryError as exc:
            dispatch.status = ProviderDispatchStatus.TEMPORARY_ERROR
            dispatch.error_payload = {"error": str(exc)}
            batch.status = SmsBatchStatus.QUEUED
            await session.commit()
            if batch.attempt_count < MAX_RETRIES:
                await _publish_retry(task)
            else:
                await _mark_batch_failed(task, "retry_exhausted")
            return
        except ProviderPermanentError as exc:
            dispatch.status = ProviderDispatchStatus.PERMANENT_ERROR
            dispatch.error_payload = {"error": str(exc)}
            await _mark_messages_failed(batch)
            await session.commit()
            return

        dispatch.status = (
            ProviderDispatchStatus.ACCEPTED if result.accepted else ProviderDispatchStatus.REJECTED
        )
        dispatch.response_payload = result.raw_response
        batch.provider_batch_id = result.provider_batch_id

        by_message_id = {item.message_id: item for item in result.messages}
        for message in batch.messages:
            item = by_message_id.get(str(message.id))
            if item is None:
                message.status = SmsMessageStatus.UNKNOWN
                continue
            message.provider_message_id = item.provider_message_id
            message.status = item.status
            message.raw_provider_status = item.raw_status

        batch.status = SmsBatchStatus.STATUS_PENDING
        mailing = await session.get(Mailing, batch.mailing_id)
        if mailing is not None:
            mailing.status = MailingStatus.SUBMITTED

        await session.commit()

        for message in batch.messages:
            if message.provider_message_id:
                await publish_status_check(
                    StatusCheckTask(
                        message_id=message.id,
                        provider_code=message.provider_code,
                        provider_message_id=message.provider_message_id,
                        correlation_id=task.correlation_id,
                    )
                )


async def _mark_messages_failed(batch: SmsBatch) -> None:
    batch.status = SmsBatchStatus.FAILED
    for message in batch.messages:
        if message.provider_message_id is None:
            message.status = SmsMessageStatus.FAILED


async def _mark_batch_failed(task: SendBatchTask, reason: str) -> None:
    async with async_session_factory() as session:
        batch = await session.scalar(
            select(SmsBatch)
            .where(SmsBatch.id == task.batch_id)
            .options(selectinload(SmsBatch.messages))
        )
        if batch is None:
            return
        await _mark_messages_failed(batch)
        session.add(
            ProviderDispatch(
                batch_id=batch.id,
                provider_code=task.provider_code,
                status=ProviderDispatchStatus.DEAD_LETTERED,
                error_payload={"reason": reason},
                retry_count=batch.attempt_count,
            )
        )
        await session.commit()


async def _publish_retry(task: SendBatchTask) -> None:
    connection = await connect()
    async with connection:
        channel = await connection.channel()
        await setup_topology(channel)
        exchange = await channel.get_exchange(topology.SEND_EXCHANGE)
        await exchange.publish(
            aio_pika.Message(
                body=task.model_dump_json().encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key=topology.SEND_RETRY_ROUTING_KEY,
        )


async def consume() -> None:
    connection = await connect()
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)
    await setup_topology(channel)
    queue = await channel.get_queue(topology.SEND_QUEUE)

    async with queue.iterator() as iterator:
        async for message in iterator:
            await _process_message(message)


async def _process_message(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        task = SendBatchTask.model_validate_json(message.body)
        await handle_send_task(task)


if __name__ == "__main__":
    asyncio.run(consume())
