import aio_pika
from aio_pika.abc import AbstractChannel, AbstractRobustConnection

from app.core.config import get_settings
from app.messaging import topology


async def connect() -> AbstractRobustConnection:
    return await aio_pika.connect_robust(get_settings().rabbitmq_url)


async def setup_topology(channel: AbstractChannel) -> None:
    send_exchange = await channel.declare_exchange(
        topology.SEND_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True
    )
    status_exchange = await channel.declare_exchange(
        topology.STATUS_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True
    )

    send_dlq = await channel.declare_queue(topology.SEND_DLQ, durable=True)
    status_dlq = await channel.declare_queue(topology.STATUS_DLQ, durable=True)
    await send_dlq.bind(send_exchange, routing_key=topology.DEAD_ROUTING_KEY)
    await status_dlq.bind(status_exchange, routing_key=topology.DEAD_ROUTING_KEY)

    send_queue = await channel.declare_queue(
        topology.SEND_QUEUE,
        durable=True,
        arguments={"x-dead-letter-exchange": topology.SEND_EXCHANGE},
    )
    send_retry_queue = await channel.declare_queue(
        topology.SEND_RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": topology.RETRY_TTL_MS,
            "x-dead-letter-exchange": topology.SEND_EXCHANGE,
            "x-dead-letter-routing-key": topology.SEND_BATCH_ROUTING_KEY,
        },
    )
    await send_queue.bind(send_exchange, routing_key=topology.SEND_BATCH_ROUTING_KEY)
    await send_retry_queue.bind(
        send_exchange, routing_key=topology.SEND_RETRY_ROUTING_KEY
    )

    status_queue = await channel.declare_queue(
        topology.STATUS_QUEUE,
        durable=True,
        arguments={"x-dead-letter-exchange": topology.STATUS_EXCHANGE},
    )
    status_retry_queue = await channel.declare_queue(
        topology.STATUS_RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": topology.RETRY_TTL_MS,
            "x-dead-letter-exchange": topology.STATUS_EXCHANGE,
            "x-dead-letter-routing-key": topology.STATUS_CHECK_ROUTING_KEY,
        },
    )
    await status_queue.bind(
        status_exchange, routing_key=topology.STATUS_CHECK_ROUTING_KEY
    )
    await status_retry_queue.bind(
        status_exchange, routing_key=topology.STATUS_RETRY_ROUTING_KEY
    )
