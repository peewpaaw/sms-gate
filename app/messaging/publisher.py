import json
import logging

import aio_pika

from app.messaging import topology
from app.messaging.rabbitmq import connect, setup_topology
from app.messaging.schemas import SendBatchTask, StatusCheckTask

logger = logging.getLogger(__name__)


async def _publish(exchange_name: str, routing_key: str, payload: dict) -> None:
    connection = await connect()
    async with connection:
        channel = await connection.channel()
        await setup_topology(channel)
        exchange = await channel.get_exchange(exchange_name)
        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload, default=str).encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key=routing_key,
        )


async def publish_send_batch(task: SendBatchTask) -> None:
    try:
        await _publish(
            topology.SEND_EXCHANGE,
            topology.SEND_BATCH_ROUTING_KEY,
            task.model_dump(mode="json"),
        )
    except OSError:
        logger.warning("rabbitmq_unavailable_send_task_not_published", extra={"task": str(task)})


async def publish_status_check(task: StatusCheckTask) -> None:
    try:
        await _publish(
            topology.STATUS_EXCHANGE,
            topology.STATUS_CHECK_ROUTING_KEY,
            task.model_dump(mode="json"),
        )
    except OSError:
        logger.warning("rabbitmq_unavailable_status_task_not_published", extra={"task": str(task)})
