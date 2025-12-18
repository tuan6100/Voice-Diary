import asyncio
import logging

from audio_transcoder.cores.config import settings
from audio_transcoder.services.transcoder import AudioTranscoderService
from shared_messaging.consumer import RabbitMQConsumer
from shared_messaging.producer import RabbitMQProducer
from shared_storage.s3 import S3Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting Audio Transcoder Worker...")

    s3 = S3Client(
        bucket=settings.S3_BUCKET_NAME,
        endpoint=settings.S3_ENDPOINT,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY
    )

    Producer = RabbitMQProducer(settings.RABBITMQ_URL)
    await Producer.connect()

    service = AudioTranscoderService(s3, Producer)

    consumer = RabbitMQConsumer(settings.RABBITMQ_URL, service_name="transcoder")
    await consumer.connect()


    await consumer.subscribe("audio_ops", "cmd.transcode", service.handle_command)

    logger.info("Transcoder is ready...")

    try:
        await asyncio.Future()
    finally:
        await consumer.close()
        await Producer.close()


if __name__ == "__main__":
    asyncio.run(main())