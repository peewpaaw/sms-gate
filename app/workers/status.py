import asyncio
import logging

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import select

from app.db.session import async_session_factory
from app.messaging import topology
from app.messaging.rabbitmq import connect, setup_topology
from app.messaging.schemas import StatusCheckTask
from app.models.enums import SmsBatchStatus
from app.models.mailing import Mailing
from app.models.sms_batch import SmsBatch
from app.models.sms_message import SmsMessage
from app.models.status_check import StatusCheck
from app.providers.base import ProviderTemporaryError
from app.providers.registry import provider_registry
from app.services.statuses import aggregate_mailing_status

logger = logging.getLogger(__name__)


async def handle_status_task(task: StatusCheckTask) -> None:
    async with async_session_factory() as session:
        message = await session.get(SmsMessage, task.message_id)
        if message is None or message.provider_message_id is None:
            logger.warning("status_message_not_found", extra={"message_id": str(task.message_id)})
            return

        adapter = provider_registry.get(task.provider_code)
        try:
            result = await adapter.get_message_status(task.provider_message_id)
        except ProviderTemporaryError:
            await _publish_retry(task)
            return

        message.status = result.status
        message.raw_provider_status = result.raw_status
        session.add(
            StatusCheck(
                message_id=message.id,
                batch_id=message.batch_id,
                provider_code=task.provider_code,
                provider_message_id=task.provider_message_id,
                raw_status=result.raw_status,
                normalized_status=result.status.value,
                response_payload=result.raw_response,
            )
        )

        if message.batch_id is not None:
            batch = await session.get(SmsBatch, message.batch_id)
            if batch is not None:
                batch.status = SmsBatchStatus.COMPLETED

        statuses = (
            await session.scalars(
                select(SmsMessage.status).where(SmsMessage.mailing_id == message.mailing_id)
            )
        ).all()
        mailing = await session.get(Mailing, message.mailing_id)
        if mailing is not None:
            mailing.status = aggregate_mailing_status(list(statuses))

        await session.commit()


async def _publish_retry(task: StatusCheckTask) -> None:
    connection = await connect()
    async with connection:
        channel = await connection.channel()
        await setup_topology(channel)
        exchange = await channel.get_exchange(topology.STATUS_EXCHANGE)
        await exchange.publish(
            aio_pika.Message(
                body=task.model_dump_json().encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key=topology.STATUS_RETRY_ROUTING_KEY,
        )


async def consume() -> None:
    connection = await connect()
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=50)
    await setup_topology(channel)
    queue = await channel.get_queue(topology.STATUS_QUEUE)

    async with queue.iterator() as iterator:
        async for message in iterator:
            await _process_message(message)


async def _process_message(message: AbstractIncomingMessage) -> None:
    async with message.process(requeue=False):
        task = StatusCheckTask.model_validate_json(message.body)
        await handle_status_task(task)


if __name__ == "__main__":
    asyncio.run(consume())
