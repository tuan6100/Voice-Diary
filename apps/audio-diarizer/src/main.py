import asyncio
import logging
import torch

from audio_diarizer.core.config import settings
from audio_diarizer.services.diarizer_service import DiarizerService
from shared_messaging.consumer import RabbitMQConsumer
from shared_messaging.producer import RabbitMQProducer
from shared_storage.s3 import S3Client


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting Audio Diarizer Worker...")
    if torch.cuda.is_available():
        logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
    else:
        logger.warning("No GPU found! Diarization will be extremely slow on CPU.")

    s3 = S3Client(
        bucket=settings.S3_BUCKET_NAME,
        endpoint=settings.S3_ENDPOINT,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY
    )
    Producer = RabbitMQProducer(settings.RABBITMQ_URL)
    await Producer.connect()
    service = DiarizerService(s3, Producer)
    consumer = RabbitMQConsumer(settings.RABBITMQ_URL, service_name="diarizer")
    await consumer.connect()
    await consumer.subscribe("audio_ops", "cmd.diarize", service.handle_command)
    logger.info("Audio Diarizer is running and waiting for tasks...")

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