import asyncio
import logging

from audio_postprocessor.cores.config import settings
from audio_postprocessor.services.postprocessor import AudioPostProcessorService
from shared_messaging.consumer import RabbitMQConsumer
from shared_messaging.producer import RabbitMQProducer
from shared_storage.s3 import S3Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting Audio Post-Processor Worker...")

    s3 = S3Client(
        bucket=settings.S3_BUCKET_NAME,
        endpoint=settings.S3_ENDPOINT,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY
    )

    producer = RabbitMQProducer(settings.RABBITMQ_URL)
    await producer.connect()

    service = AudioPostProcessorService(s3, producer)

    consumer = RabbitMQConsumer(settings.RABBITMQ_URL, service_name="postprocessor")
    await consumer.connect()
    await consumer.subscribe("audio_ops", "cmd.postprocess", service.handle_command)

    logger.info("Post-Processor ready.")

    try:
        await asyncio.Future()
    finally:
        await consumer.close()
        await producer.close()

if __name__ == "__main__":
    asyncio.run(main())