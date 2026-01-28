import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response, Depends
from beanie import PydanticObjectId
from redis.asyncio import Redis
from starlette.responses import PlainTextResponse

from audio_api.cores.injectable import get_redis, get_current_user_id, get_s3_client
from audio_api.models.audio import Audio
from audio_api.utils.transcript_converter import generate_webvtt, generate_plain_text
from shared_storage.s3 import S3Client

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
    audio = await Audio.get(audio_id)
    if not audio:
        raise HTTPException(404, "Audio not found")
    if audio.audio_meta and audio.audio_meta.google_doc_id:
        return {
            "status": "exists",
            "message": "Document already exists",
            "doc_link": f"https://docs.google.com/document/d/{audio.audio_meta.google_doc_id}/edit"
        }

    token_key = f"google_token:{user_id}"
    google_token = await redis.get(token_key)
    if not google_token:
        raise HTTPException(401, "Google Session expired. Please login again.")
    try:
        from audio_api.services.google_docs import GoogleDocsService
        doc_service = GoogleDocsService(access_token=google_token.decode('utf-8'))
        doc = doc_service.create_transcript_doc(
            title=audio.caption or "Untitled Audio",
            transcript=audio.transcript
        )
        doc_id = doc['document_id']
        if not audio.audio_meta:
            from audio_api.models.audio import AudioMetadata
            audio.audio_meta = AudioMetadata()
        audio.audio_meta.google_doc_id = doc_id
        await audio.save()
        return {
            "status": "created",
            "message": "Transcript exported to Google Docs",
            "doc_link": f"https://docs.google.com/document/d/{doc_id}/edit"
        }
    except Exception as e:
        raise HTTPException(500, f"Export failed: {str(e)}")


@router.put("/{audio_id}/sync-google-docs")
async def edit_transcript(
        audio_id: PydanticObjectId,
        user_id: str = Depends(get_current_user_id),
        redis: Redis = Depends(get_redis),
        s3: S3Client = Depends(get_s3_client)
):
    audio = await Audio.get(audio_id)
    if not audio:
        raise HTTPException(404, "Audio not found")

    if not audio.audio_meta or not audio.audio_meta.google_doc_id:
        raise HTTPException(400, "This audio has not been linked to any Google Doc yet.")

    token_key = f"google_token:{user_id}"
    google_token = await redis.get(token_key)
    if not google_token:
        raise HTTPException(401, "Google Session expired. Please login again.")

    try:
        from audio_api.services.google_docs import GoogleDocsService
        from audio_api.services.transcript_s3_sync import TranscriptS3SyncService
        doc_service = GoogleDocsService(access_token=google_token.decode('utf-8'))
        raw_text = doc_service.get_document_content(audio.audio_meta.google_doc_id)
        new_transcript = doc_service.parse_transcript_from_text(raw_text)
        if not new_transcript:
            raise HTTPException(400, "Could not parse transcript. Please preserve [MM:SS] timestamps.")
        audio.transcript = new_transcript
        await audio.save()
        if not audio.job_id:
            raise HTTPException(400, "Audio does not have a job_id; cannot sync transcript artifacts.")
        sync_service = TranscriptS3SyncService(s3)
        sync_result = await sync_service.sync_edited_transcript(
            job_id=audio.job_id,
            transcript_segments=new_transcript,
        )
        return {
            "status": "synced",
            "message": "Transcript updated from Google Docs and synced to S3",
            "segments_count": sync_result.segments_count,
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(500, f"Sync failed: {str(e)}")