import asyncio
import logging
from redis.asyncio import Redis

from audio_orchestrator.cores.config import settings
from audio_orchestrator.services.state_manager import StateManager
from audio_orchestrator.services.workflow import WorkflowOrchestrator
from shared_messaging.consumer import RabbitMQConsumer
from shared_messaging.producer import RabbitMQProducer
from shared_storage.s3 import S3Client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting Audio Orchestrator...")

    # Setup Infrastructure
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    # Producer
    producer = RabbitMQProducer(settings.RABBITMQ_URL)
    await producer.connect()

    # Consumer (Chỉ cần 1 instance, lib đã tự tách queue)
    consumer = RabbitMQConsumer(settings.RABBITMQ_URL, service_name="orchestrator")
    await consumer.connect()

    # Setup Services
    s3 = S3Client(
        bucket=settings.S3_BUCKET_NAME,
        endpoint=settings.S3_ENDPOINT,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY
    )
    state_manager = StateManager(redis)
    workflow = WorkflowOrchestrator(producer, state_manager, s3)

    await consumer.subscribe("media_events", "file.uploaded", workflow.handle_file_uploaded)
    await consumer.subscribe("worker_events", "preprocess.done", workflow.handle_preprocess_done)
    await consumer.subscribe("worker_events", "segment.done", workflow.handle_segment_done)
    await consumer.subscribe("worker_events", "enhancement.done", workflow.handle_enhancement_done)
    await consumer.subscribe("worker_events", "recognition.done", workflow.handle_recognition_done)
    await consumer.subscribe("worker_events", "diarization.done", workflow.handle_diarization_done)
    await consumer.subscribe("worker_events", "transcode.done", workflow.handle_transcode_done)
    await consumer.subscribe("worker_events", "job.finalized", workflow.handle_job_finalized)

    logger.info("Orchestrator is running with ISOLATED QUEUES per handler...")

    try:
        await asyncio.Future()
    finally:
        await producer.close()
        await consumer.close()
        await redis.close()


if __name__ == "__main__":
    asyncio.run(main())