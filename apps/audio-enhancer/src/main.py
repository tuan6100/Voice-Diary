import asyncio
import logging
import sys

from audio_enhancer.cores.config import settings
from audio_enhancer.services.enhancer import AudioEnhancerService
from shared_messaging.consumer import RabbitMQConsumer
from shared_messaging.producer import RabbitMQProducer
from shared_storage.s3 import S3Client


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting Audio Enhancer Worker...")
    s3 = S3Client(
        bucket=settings.S3_BUCKET_NAME,
        endpoint=settings.S3_ENDPOINT,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY
    )

    Producer = RabbitMQProducer(settings.RABBITMQ_URL)
    await Producer.connect()

    service = AudioEnhancerService(s3, Producer)
    consumer = RabbitMQConsumer(settings.RABBITMQ_URL, service_name="enhancer")
    await consumer.connect()
    await consumer.subscribe("audio_ops", "cmd.enhance", service.handle_command)

    logger.info("Audio Enhancer is running and waiting for tasks...")

    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        logger.info("Stopping worker...")
    finally:
        await consumer.close()
        await Producer.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")