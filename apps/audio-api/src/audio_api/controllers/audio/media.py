from fastapi import APIRouter, HTTPException, Response, Depends
from beanie import PydanticObjectId
from redis.asyncio import Redis
from starlette.responses import PlainTextResponse

from audio_api.cores.injectable import get_redis, get_current_user_id
from audio_api.models.audio import Audio
from audio_api.utils.transcript_converter import generate_webvtt, generate_plain_text

router = APIRouter()


@router.get("/{audio_id}/stream")
async def get_stream_info(audio_id: PydanticObjectId):
    audio = await Audio.get(audio_id)
    if not audio or not audio.audio_meta.hls_url:
        raise HTTPException(404, "Stream not ready")
    return {
        "stream_url": audio.audio_meta.hls_url,
        "duration": audio.audio_meta.duration
    }


@router.get("/{audio_id}/captions.vtt", response_class=PlainTextResponse)
async def get_captions(audio_id: PydanticObjectId):
    audio = await Audio.get(audio_id)
    if not audio:
        raise HTTPException(404)

    return generate_webvtt(audio.transcript)


@router.get("/{audio_id}/download")
async def download_transcript(audio_id: PydanticObjectId, format: str = "txt"):
    audio = await Audio.get(audio_id)
    if not audio:
        raise HTTPException(404)
    if format == "vtt":
        content = generate_webvtt(audio.transcript)
        ext = "vtt"
    else:
        content = generate_plain_text(audio.transcript)
        ext = "txt"
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={audio_id}.{ext}"}
    )


@router.post("/{audio_id}/export/google-docs")
async def export_to_google_docs(
        audio_id: PydanticObjectId,
        user_id: str = Depends(get_current_user_id),
        redis: Redis = Depends(get_redis)
):
    """
    Xuất Transcript sang Google Docs của người dùng.
    """
    audio = await Audio.get(audio_id)
    if not audio:
        raise HTTPException(404, "Audio not found")
    token_key = f"google_token:{user_id}"
    google_token = await redis.get(token_key)
    if not google_token:
        raise HTTPException(401, "Google Session expired. Please login again.")
    try:
        from audio_api.services.google_docs import GoogleDocsService
        doc_service = GoogleDocsService(access_token=google_token.decode('utf-8'))
        doc_link = doc_service.create_transcript_doc(
            title=audio.caption or "Untitled Audio",
            transcript=audio.transcript
        )
        return {
            "status": "success",
            "message": "Transcript exported to Google Docs",
            "doc_link": doc_link
        }

    except Exception as e:
        raise HTTPException(500, f"Export failed: {str(e)}")