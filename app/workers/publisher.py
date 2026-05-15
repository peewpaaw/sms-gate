import json
import logging
import aio_pika

from app.messaging.rabbitmq import connect, setup_topology
from app.messaging.schemas import SendBatchTask
from app.messaging import topology


logger = logging.getLogger(__name__)


async def _publish(exchange_name: str, routing_key: str, payload: dict) -> None:
    connection = await connect()
    async with connection:
        channel = await connection.channel()
        await setup_topology(channel)
        exchange = await channel.get_exchange(exchange_name)
        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload, default=str).endcode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            ),
            routing_key=routing_key,
        )


async def publish_send_batch(task: SendBatchTask) -> None:
    try:
        await _publish(
            exchange_name=topology.SEND_EXCHANGE,
            routing_key=topology.SEND_QUEUE,
            payload=task.model_dump(mode="json"),
        )
    except OSError:
        logger.error("Failed to publish send mailing task", extra={"task": str(task)})


async def publish() -> None:
    connection = await connect()
    channel = await connection.chanel()
    