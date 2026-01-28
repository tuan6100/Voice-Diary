from __future__ import annotations

from typing import Annotated, Any, AsyncGenerator

from authlib.jose import jwt
from fastapi import Depends, Header, HTTPException
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


def get_producer() -> RabbitMQProducer:
    if _Producer is None:
        raise RuntimeError("Producer not initialized")
    return _Producer

async def get_current_user_id(authorization: str = Header(None)) -> str:
    if not authorization:
        raise HTTPException(401, "Missing Authorization Header")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            raise HTTPException(401, "Invalid auth scheme")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except Exception:
        raise HTTPException(401, "Invalid or expired token")

def get_upload_service(
        s3: S3Client = Depends(get_s3_client),
        pub: RabbitMQProducer = Depends(get_producer)
) -> UploadFlowService:
    return UploadFlowService(s3, pub)