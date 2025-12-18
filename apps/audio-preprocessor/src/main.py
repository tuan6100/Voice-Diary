import asyncio
import logging

from audio_preprocessor.cores.config import settings
from audio_preprocessor.services.processor import AudioProcessorService
from shared_messaging.consumer import RabbitMQConsumer
from shared_messaging.producer import RabbitMQProducer
from shared_storage.s3 import S3Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting Audio Preprocessor Worker...")


    s3 = S3Client(
        bucket=settings.S3_BUCKET_NAME,
        endpoint=settings.S3_ENDPOINT,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY
    )


    Producer = RabbitMQProducer(settings.RABBITMQ_URL)
    await Producer.connect()


    service = AudioProcessorService(s3, Producer)


    consumer = RabbitMQConsumer(settings.RABBITMQ_URL, service_name="preprocessor")
    await consumer.connect()



    await consumer.subscribe("audio_ops", "cmd.preprocess", service.handle_command)

    logger.info("Preprocessor is waiting for tasks...")

    try:
        await asyncio.Future()
    finally:
        await consumer.close()
        await Producer.close()


if __name__ == "__main__":
    asyncio.run(main())