import logging
import json
import asyncio
from audio_orchestrator.services.state_manager import StateManager, JobStatus
from shared_storage.s3 import S3Client
from shared_messaging.producer import RabbitMQProducer
from shared_schemas.events import JobFailedEvent, JobCancelledEvent

logger = logging.getLogger(__name__)


class FailureHandlerService:
    def __init__(self, state_manager: StateManager, s3: S3Client, producer: RabbitMQProducer):
        self.state = state_manager
        self.s3 = s3
        self.producer = producer

    async def terminate_job(self, job_id: str, status: JobStatus, reason: str):
        logger.warning(f"TERMINATING JOB {job_id}: {status} - {reason}")
        await self.state.update_progress(job_id, status, 0, reason)
        try:
            if status == JobStatus.FAILED:
                event = JobFailedEvent(job_id=job_id, reason=reason)
                await self.producer.publish("audio_events", "event.job_failed", event)
            elif status == JobStatus.CANCELLED:
                event = JobCancelledEvent(job_id=job_id, reason=reason)
                await self.producer.publish("audio_events", "event.job_cancelled", event)
        except Exception as e:
            logger.error(f"Failed to publish termination event for {job_id}: {e}")
        # TODO: Move this to a dedicated notification service or Audio API
        notification_title = "Job processing failed" if status == JobStatus.FAILED else "Job processing cancelled"
        job_info = await self.state.redis.hgetall(f"job:{job_id}")
        user_id = job_info.get("user_id")
        if user_id:
            await self.send_push_notification(user_id, notification_title, reason)
        await self._cleanup_resources(job_id)

    async def _cleanup_resources(self, job_id: str):
        logger.info(f"Cleaning up resources for {job_id}...")
        folders_to_clean = [
            f"raw/{job_id}/",
            f"segments/{job_id}/",
            f"transcripts/{job_id}/",
            f"enhanced/{job_id}/",
            f"analysis/{job_id}/",
            f"hls/{job_id}/",
            f"results/{job_id}/",
            f"tmp/{job_id}/"
        ]

        tasks = [self.s3.delete_folder(folder) for folder in folders_to_clean]
        await asyncio.gather(*tasks)
        logger.info(f"Cleanup finished for {job_id}")


    async def handle_dlq_message(self, body: bytes):
        try:
            message_dict = json.loads(body)
            job_id = message_dict.get("job_id")
            if not job_id: return

            await self.terminate_job(
                job_id,
                JobStatus.FAILED,
                "System Error: Processing failed and rolled back."
            )
        except Exception as e:
            logger.error(f"Failed to process DLQ message: {e}")

    async def handle_cancellation_command(self, cmd_data: dict):
        job_id = cmd_data.get("job_id")
        reason = cmd_data.get("reason", "Cancelled by user")
        await self.terminate_job(
            job_id,
            JobStatus.CANCELLED,
            reason
        )

    async def send_push_notification(self, user_id: str, title: str, body: str):
        # Mockup FCM
        logger.info(f"PUSH to {user_id}: [{title}] {body}")