import uuid
import logging
from datetime import datetime, timezone, timedelta

from redis.asyncio import Redis

from audio_api.dtos.response.upload import UploadInitResponse
from audio_api.models.audio import ProcessingStatus, Audio, AudioMetadata
from audio_api.models.post import Post
from shared_messaging.producer import RabbitMQProducer
from shared_storage.s3 import S3Client

from shared_schemas.events import FileUploadedEvent


logger = logging.getLogger(__name__)


class UploadFlowService:
    def __init__(self, s3: S3Client, producer: RabbitMQProducer):
        self.s3 = s3
        self.Producer = producer

    async def create_upload_session(self, filename: str, content_type: str, user_id: str, redis: Redis):
        job_id = str(uuid.uuid4())
        date_prefix = datetime.now(tz=timezone(timedelta(hours=7))).strftime('%Y-%m-%d')
        object_key = f"raw/{date_prefix}/{job_id}/{filename}"
        url = self.s3.generate_presigned_url(
            object_key=object_key,
            content_type=content_type
        )
        async with redis.pipeline() as pipe:
            redis_key = f"job:{job_id}"
            await pipe.hset(redis_key, mapping={
                "job_id": job_id,
                "user_id": user_id,
                "status": "UPLOADING",
                "filename": filename,
                "storage_path": object_key,
                "progress": 0,
                "created_at": datetime.now().isoformat()
            })
            await pipe.expire(redis_key, 3600)
            await pipe.execute()

        return UploadInitResponse(
            job_id=job_id,
            file_name=filename,
            presigned_url=url,
            expires_in=3600
        )

    async def trigger_processing(self, user_id: str, job_id: str, title: str = "Untitled", duration: float = 0.0, file_size: int = 0):
        new_audio = Audio(
            user_id=user_id,
            job_id=job_id,
            status=ProcessingStatus.PENDING,
            caption="New Recording",
            created_at=datetime.now(timezone.utc),
            transcript=[],
            audio_meta= AudioMetadata(
                duration=duration,
                file_size=file_size
            )
        )
        await new_audio.insert()
        new_post = Post(
            user_id=user_id,
            audio_id=str(new_audio.id),
            title=title,
            uploaded_date=datetime.now(timezone.utc),
            views_count=0
        )
        await new_post.insert()
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