import asyncio
import logging
import torch

from audio_recognizer.cores.config import settings
from audio_recognizer.services.recognizer import AudioRecognizerService
from audio_recognizer.utils.whisper_engine import WhisperEngine
from shared_messaging.consumer import RabbitMQConsumer
from shared_messaging.producer import RabbitMQProducer
from shared_storage.s3 import S3Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting Audio Recognizer Worker...")
    if torch.cuda.is_available():
        logger.info(f"GPU Detected: {torch.cuda.get_device_name(0)}")
    else:
        logger.warning("No GPU found. Whisper Large-v3 will be extremely slow!")

    try:
        WhisperEngine.get_instance()
    except Exception as e:
        logger.critical(f"Failed to load Whisper Model: {e}")
        return

    s3 = S3Client(
        bucket=settings.S3_BUCKET_NAME,
        endpoint=settings.S3_ENDPOINT,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY
    )

    Producer = RabbitMQProducer(settings.RABBITMQ_URL)
    await Producer.connect()

    consumer = RabbitMQConsumer(settings.RABBITMQ_URL, service_name="recognizer")
    await consumer.connect()

    service = AudioRecognizerService(s3, Producer)
    await consumer.subscribe("audio_ops", "cmd.recognize", service.handle_command)

    logger.info("Recognizer is ready to transcribe...")
    try:
        await asyncio.Future()
    finally:
        await consumer.close()
        await Producer.close()


if __name__ == "__main__":
    asyncio.run(main())