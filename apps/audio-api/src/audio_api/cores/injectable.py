from __future__ import annotations

from typing import Annotated, Any, AsyncGenerator

from fastapi import Depends, Header
from redis.asyncio import Redis

from audio_api.cores.config import settings
from audio_api.cores.redis import get_redis_client
from audio_api.services.upload_flow import UploadFlowService
from shared_messaging.producer import RabbitMQProducer
from shared_storage.s3 import S3Client

def get_s3_client() -> S3Client:
    return S3Client(
        bucket=settings.S3_BUCKET_NAME,
        endpoint=settings.S3_ENDPOINT,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY
    )

async def get_redis() -> AsyncGenerator[Redis, Any]:
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.close()


_Producer: RabbitMQProducer | None = None


def get_Producer() -> RabbitMQProducer:
    if _Producer is None:
        raise RuntimeError("Producer not initialized")
    return _Producer

async def get_current_user_id(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization:
        return "user_demo_123"
    return "user_from_token"

def get_upload_service(
        s3: S3Client = Depends(get_s3_client),
        pub: RabbitMQProducer = Depends(get_Producer)
) -> UploadFlowService:
    return UploadFlowService(s3, pub)