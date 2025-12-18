from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis

from audio_api.cores.injectable import get_current_user_id, get_redis

router = APIRouter()


@router.get("/{job_id}")
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
    # if job_data.get("user_id") and job_data.get("user_id") != user_id:
    #     raise HTTPException(status_code=403, detail="Not authorized to view this job")

    return {
        "job_id": job_id,
        "status": job_data.get("status", "UNKNOWN"),
        "progress": int(job_data.get("progress", 0)),
        "message": job_data.get("message", "")
    }