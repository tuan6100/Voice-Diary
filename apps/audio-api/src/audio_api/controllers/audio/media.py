from fastapi import APIRouter, HTTPException, Response
from beanie import PydanticObjectId
from starlette.responses import PlainTextResponse

# Import model Audio (Dùng chung thư viện shared hoặc copy model)
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