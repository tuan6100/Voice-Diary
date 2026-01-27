import uuid
import logging
from datetime import datetime, timezone, timedelta

from audio_api.models.audio import ProcessingStatus, Audio
from shared_messaging.producer import RabbitMQProducer
from shared_storage.s3 import S3Client

from shared_schemas.events import FileUploadedEvent


logger = logging.getLogger(__name__)


class UploadFlowService:
    def __init__(self, s3: S3Client, producer: RabbitMQProducer):
        self.s3 = s3
        self.Producer = producer

    async def create_upload_session(self, filename: str, content_type: str):
        job_id = str(uuid.uuid4())
        date_prefix = datetime.now(tz=timezone(timedelta(hours=7))).strftime('%Y-%m-%d')
        object_key = f"raw/{date_prefix}/{job_id}/{filename}"

        url = self.s3.generate_presigned_url(
            object_key=object_key,
            content_type=content_type
        )

        return {
            "job_id": job_id,
            "presigned_url": url,
            "storage_path": object_key
        }

    async def trigger_processing(self, user_id: str, job_id: str):
        new_audio = Audio(
            user_id=user_id,
            job_id=job_id,
            status=ProcessingStatus.PENDING,
            caption="New Recording",
            created_at=datetime.now(datetime.UTC) ,
            transcript=[],
        )
        # Beanie insert
        await new_audio.insert()
        event = FileUploadedEvent(
            job_id=job_id,
            user_id=user_id,
            storage_path=f"raw/{datetime.now(tz=timezone(timedelta(hours=7))).strftime('%Y-%m-%d')}/{job_id}/"
        )
        logger.info('trigger processing...')
        await self.Producer.publish(
            exchange_name="media_events",
            routing_key="file.uploaded",
            message=event
        )

        logger.info(f"Triggered processing for Job {job_id} by User {user_id}")
        return {"status": "queued"}