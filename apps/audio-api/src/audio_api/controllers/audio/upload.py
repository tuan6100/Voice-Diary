from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis

from audio_api.cores.injectable import get_upload_service, get_current_user_id, get_redis
from audio_api.dtos.request.upload import UploadInitRequest
from audio_api.dtos.response.upload import UploadInitResponse
from audio_api.services.upload_flow import UploadFlowService

router = APIRouter()

@router.post("/init", response_model=UploadInitResponse)
async def init_upload(
        request: UploadInitRequest,
        service: UploadFlowService = Depends(get_upload_service)
):
    """
    Client gọi API này trước.
    Nhận về Presigned URL để upload trực tiếp lên S3.
    """
    result = await service.create_upload_session(
        filename=request.filename,
        content_type=request.content_type
    )
    return result

@router.post("/{job_id}/confirm")
async def confirm_upload(
        job_id: str,
        user_id: str = Depends(get_current_user_id),
        service: UploadFlowService = Depends(get_upload_service)
):
    """
    Client gọi API này sau khi đã PUT file thành công lên S3.
    Server sẽ bắn Event để các worker bắt đầu xử lý.
    """
    result = await service.trigger_processing(user_id, job_id)
    return result

@router.get("/progress/{job_id}")
async def get_upload_status(
        job_id: str,
        redis: Redis = Depends(get_redis)
):
    redis_key = f"job:{job_id}"
    job_data = await redis.hgetall(redis_key)
    print(f"Job data: {job_data}")
    print(f"Type: {type(job_data)}")
    print(f"Empty check: {not job_data}")

    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found or expired")

    return {
        "job_id": job_id,
        "status": job_data.get("status", "UNKNOWN"),
        "progress": int(job_data.get("progress", 0)),
        "message": job_data.get("message", "")
    }