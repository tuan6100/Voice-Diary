from __future__ import annotations

import logging
import aio_pika
import json
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class RabbitMQProducer:
    def __init__(self, amqp_url: str):
        self.amqp_url = amqp_url
        self.connection: aio_pika.RobustConnection | None = None
        self.channel: aio_pika.RobustChannel | None = None
        self.exchanges = {}

    async def connect(self):
        logger.info("Connecting to RabbitMQ at %s", self.amqp_url)
        self.connection = await aio_pika.connect_robust(self.amqp_url, heartbeat=300)
        self.channel = await self.connection.channel()
        self.exchanges = {}
        logger.info("RabbitMQ Producer connected & Exchange cache cleared")

    async def close(self):
        if self.connection:
            await self.connection.close()

    async def publish(self, exchange_name: str, routing_key: str, message: BaseModel | dict):
        if not self.connection or self.connection.is_closed:
            logger.warning("Connection lost, reconnecting...")
            await self.connect()

        if not self.channel or self.channel.is_closed:
            logger.warning("Channel lost, recreating...")
            self.channel = await self.connection.channel()
            self.exchanges = {}

        if exchange_name not in self.exchanges:
            exchange = await self.channel.declare_exchange(
                exchange_name,
                type=aio_pika.ExchangeType.TOPIC,
                durable=True
            )
            self.exchanges[exchange_name] = exchange
        else:
            exchange = self.exchanges[exchange_name]

        if isinstance(message, BaseModel):
            body = message.model_dump_json().encode()
        else:
            body = json.dumps(message).encode()

        await exchange.publish(
            aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT
            ),
            routing_key=routing_key
        )
        logger.debug(f"Published to {exchange_name}/{routing_key}")