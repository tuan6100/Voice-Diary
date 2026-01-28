import json
import logging
from redis.asyncio import Redis
from enum import Enum

logger = logging.getLogger(__name__)

class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PREPROCESSING = "PREPROCESSING"
    SEGMENTING = "SEGMENTING"
    RECOGNIZING = "RECOGNIZING"
    TRANSCODING = "TRANSCODING"
    PROCESSING = "PROCESSING"
    POST_PROCESSING = "POST_PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class StateManager:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.ttl = 3600

    async def init_job(self, job_id: str, user_id: str):
        key = f"job:{job_id}"
        data = {
            "user_id": user_id,
            "status": JobStatus.QUEUED.value,
            "progress": 0,
            "message": "Starting..."
        }
        await self.redis.hset(key, mapping=data)
        await self.redis.expire(key, self.ttl)

    async def update_progress(self, job_id: str, status: JobStatus, progress: int, message: str = ""):
        await self.redis.hmset(f"job:{job_id}", {
            "status": status,
            "progress": str(progress),
            "message": message
        })
        channel_name = f"job_progress:{job_id}"
        payload = json.dumps({
            "job_id": job_id,
            "status": status,
            "progress": progress,
            "message": message
        })
        await self.redis.publish(channel_name, payload)
        logger.info(f"Job {job_id}: {status} - {progress}%")

    async def get_job_status(self, job_id: str) -> str | None:
        key = f"job:{job_id}"
        status = await self.redis.hget(key, "status")
        if status is None:
            return None
        return status.decode() if isinstance(status, (bytes, bytearray)) else status
