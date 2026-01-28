from __future__ import annotations

import asyncio
import json
import logging
import aio_pika
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class RabbitMQConsumer:
    def __init__(self, amqp_url: str, service_name: str):
        self.amqp_url = amqp_url
        self.service_name = service_name
        self.connection: aio_pika.RobustConnection | None = None
        self.channel: aio_pika.RobustChannel | None = None

    async def connect(self):
        self.connection = await aio_pika.connect_robust(self.amqp_url, heartbeat=600)
        self.channel = await self.connection.channel()
        await self.channel.set_qos(prefetch_count=1)
        logger.info(f"RabbitMQ Consumer ({self.service_name}) connected")

    async def close(self):
        if self.connection:
            await self.connection.close()

    async def subscribe(
            self,
            exchange_name: str,
            routing_key: str,
            handler: Callable[[dict], Awaitable[None]],
            *,
            max_retries: int = 3,
            dlq_suffix: str = ".dlq"
    ):
        if not self.channel:
            raise RuntimeError("Please call connect() before subscribe()")

        exchange = await self.channel.declare_exchange(
            exchange_name,
            type=aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        dlq_exchange_name = f"{exchange_name}{dlq_suffix}"
        dlq_exchange = await self.channel.declare_exchange(
            dlq_exchange_name,
            type=aio_pika.ExchangeType.TOPIC,
            durable=True
        )

        safe_key = routing_key.replace(".", "_").replace("*", "all")
        queue_name = f"{self.service_name}.{exchange_name}.{safe_key}.queue"
        dlq_queue_name = f"{self.service_name}.{dlq_exchange_name}.{safe_key}.queue"

        queue = await self.channel.declare_queue(queue_name, durable=True)
        await queue.bind(exchange, routing_key=routing_key)

        dlq_queue = await self.channel.declare_queue(dlq_queue_name, durable=True)
        await dlq_queue.bind(dlq_exchange, routing_key=routing_key)

        logger.info(f"Bound queue '{queue_name}' to '{exchange_name}' with key '{routing_key}'")
        logger.info(f"Bound DLQ '{dlq_queue_name}' to '{dlq_exchange_name}' with key '{routing_key}'")

        async def on_message(message: aio_pika.IncomingMessage):
            should_ack = False
            should_reject = False

            try:
                data = json.loads(message.body.decode())
                await handler(data)
                should_ack = True
            except Exception as e:
                logger.exception(f"Handler failed for queue '{queue_name}': {e}")
                try:
                    headers = dict(message.headers or {})
                    retry_count = int(headers.get("x-retry", 0))

                    if self.channel.is_closed:
                        logger.error(f"Channel is closed, reconnecting...")
                        await self.connect()
                        exchange = await self.channel.declare_exchange(
                            exchange_name,
                            type=aio_pika.ExchangeType.TOPIC,
                            durable=True
                        )
                        dlq_exchange = await self.channel.declare_exchange(
                            dlq_exchange_name,
                            type=aio_pika.ExchangeType.TOPIC,
                            durable=True
                        )

                    if retry_count < max_retries:
                        headers["x-retry"] = retry_count + 1
                        republish_msg = aio_pika.Message(
                            body=message.body,
                            headers=headers,
                            content_type=message.content_type,
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                        )
                        await exchange.publish(republish_msg, routing_key=routing_key)
                        logger.warning(
                            f"Handler failed for queue '{queue_name}'. Retry {retry_count + 1}/{max_retries}"
                        )
                    else:
                        dlq_msg = aio_pika.Message(
                            body=message.body,
                            headers={**headers, "x-retry": retry_count},
                            content_type=message.content_type,
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
                        )
                        await dlq_exchange.publish(dlq_msg, routing_key=routing_key)
                        logger.error(
                            f"Message moved to DLQ '{dlq_queue_name}' after {retry_count} retries"
                        )
                    should_ack = True
                except Exception as republish_error:
                    logger.exception(f"Failed to republish message from {queue_name}: {republish_error}")
                    should_reject = True

            finally:
                try:
                    if should_ack:
                        await message.ack()
                    elif should_reject:
                        await message.reject(requeue=False)
                except Exception as ack_error:
                    logger.exception(f"Failed to ack/reject message: {ack_error}")

        def callback(message: aio_pika.IncomingMessage):
            asyncio.create_task(on_message(message))

        await self.channel.set_qos(prefetch_count=1)
        await queue.consume(callback)