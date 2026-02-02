import json

from fastapi import APIRouter, Depends, HTTPException, Request
from redis.asyncio import Redis
from sse_starlette import EventSourceResponse

from audio_api.cores.injectable import get_upload_service, get_current_user_id, get_redis, get_producer
from audio_api.dtos.request.upload import UploadInitRequest, UploadConfirmRequest
from audio_api.dtos.response.upload import UploadInitResponse
from audio_api.models.audio import Audio
from audio_api.models.post import Post
from audio_api.services.upload_flow import UploadFlowService
from shared_messaging.producer import RabbitMQProducer

router = APIRouter()

@router.post("/init", response_model=UploadInitResponse)
async def init_upload(
        request: UploadInitRequest,
        service: UploadFlowService = Depends(get_upload_service),
        user_id: str = Depends(get_current_user_id),
        redis: Redis = Depends(get_redis)
):
    result = await service.create_upload_session(
        filename=request.filename,
        content_type=request.content_type,
        user_id=user_id,
        redis=redis
    )
    return result

@router.post("/confirm")
async def confirm_upload(
        request: UploadConfirmRequest,
        user_id: str = Depends(get_current_user_id),
        service: UploadFlowService = Depends(get_upload_service),
        redis: Redis = Depends(get_redis)
):
    redis_key = f"job:{request.job_id}"
    job_data = await redis.hgetall(redis_key)
    if not job_data:
        raise HTTPException(404, "Job not found or expired")
    job_owner = job_data.get(b"user_id", job_data.get("user_id"))
    if job_owner:
        job_owner = job_owner.decode('utf-8') if isinstance(job_owner, bytes) else job_owner
        if job_owner != user_id:
            raise HTTPException(403, "You don't have permission to confirm this upload")
    result = await service.trigger_processing(user_id, request.job_id, request.title, request.duration, request.file_size)
    return result


@router.post("/{job_id}/cancel")
async def cancel_job(
        job_id: str,
        user_id: str = Depends(get_current_user_id),
        redis: Redis = Depends(get_redis),
        producer: RabbitMQProducer = Depends(get_producer)
):
    redis_key = f"job:{job_id}"
    job_data = await redis.hgetall(redis_key)
    if not job_data:
        raise HTTPException(404, "Job not found")
    job_owner = job_data.get(b"user_id", job_data.get("user_id"))
    if isinstance(job_owner, bytes): job_owner = job_owner.decode()
    if job_owner != user_id:
        raise HTTPException(403, "Permission denied")
    current_status = job_data.get(b"status", job_data.get("status"))
    if isinstance(current_status, bytes): current_status = current_status.decode()
    if current_status in ["COMPLETED", "FAILED", "CANCELLED"]:
        raise HTTPException(400, f"Cannot cancel job in status {current_status}")
    await redis.hset(f"job:{job_id}", "status", "CANCELLING")
    cancel_cmd = {"job_id": job_id, "reason": "User request"}
    await producer.publish(
        exchange_name="audio_ops",
        routing_key="cmd.cancel",
        message=cancel_cmd
    )
    audio = await Audio.find_one(Audio.job_id == job_id)
    if audio:
        await Post.find_one(Post.audio_id == str(audio.id)).delete()
        await audio.delete()
    return {"status": "success", "message": "Cancellation request sent"}

@router.get("/progress/{job_id}")
async def get_upload_status(
        job_id: str,
        user_id: str = Depends(get_current_user_id),
        redis: Redis = Depends(get_redis)
):
    redis_key = f"job:{job_id}"
    job_data = await redis.hgetall(redis_key)
    print(f"Job data: {job_data}")
    print(f"Type: {type(job_data)}")
    print(f"Empty check: {not job_data}")
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    job_owner = job_data.get(b"user_id", job_data.get("user_id"))
    if job_owner:
        job_owner = job_owner.decode('utf-8') if isinstance(job_owner, bytes) else job_owner
        if job_owner != user_id:
            raise HTTPException(403, "You don't have permission to view this job")
    return {
        "job_id": job_id,
        "status": job_data.get("status", "UNKNOWN"),
        "progress": int(job_data.get("progress", 0)),
        "message": job_data.get("message", "")
    }


@router.get("/progress/{job_id}/stream")
async def stream_progress(
        job_id: str,
        request: Request,
        redis: Redis = Depends(get_redis)
):
    """
    Client sẽ connect vào đây để lắng nghe sự kiện.
    """
    async def event_generator():
        pubsub = redis.pubsub()
        channel_name = f"job_progress:{job_id}"
        await pubsub.subscribe(channel_name)
        try:
            current_data = await redis.hgetall(f"job:{job_id}")
            if current_data:
                decoded = {}
                for k, v in current_data.items():
                    key = k.decode() if isinstance(k, bytes) else k
                    value = v.decode() if isinstance(v, bytes) else v
                    decoded[key] = value
                yield {
                    "event": "update",
                    "data": json.dumps(decoded)
                }
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break
                if message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")

                    yield {
                        "event": "update",
                        "data": data
                    }
                    parsed = json.loads(data)
                    if parsed.get("status") in ["COMPLETED", "FAILED"]:
                        yield {"event": "close", "data": "Stream closed"}
                        break
        except Exception as e:
            yield {"event": "error", "data": str(e)}
        finally:
            await pubsub.unsubscribe(channel_name)
    return EventSourceResponse(event_generator())