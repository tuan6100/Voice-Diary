from datetime import datetime
from typing import List, Optional

from pydantic import Field

from audio_api.cores.config import settings
from audio_api.cores.model import CamelModel
from audio_api.models.audio import Audio
from audio_api.models.post import Post


class PostResponse(CamelModel):
    id: str
    title: str
    duration: float = 0.0
    file_size: int = 0
    record_date: Optional[datetime] = None
    upload_date: datetime
    mood: Optional[str] = None
    album_id: Optional[str] = None
    hashtags: List[str] = []
    text_content: Optional[str] = None
    thumbnail_url: Optional[str] = None
    attachedImageUrls: List[str] = []
    stream_url: Optional[str] = None

class ToggleLikeResponse(CamelModel):
    likes: int = Field(..., ge=0)


class IncreaseViewResponse(CamelModel):
    status: str


def build_post_response(post: Post, audio: Optional[Audio]) -> PostResponse:
    duration = 0.0
    transcript_text = ""
    file_size = 0
    stream_url = None

    if audio:
        if audio.audio_meta:
            duration = audio.audio_meta.duration or 0.0
            file_size = getattr(audio.audio_meta, "size", 0)
        if audio.transcript and len(audio.transcript) > 0:
            segments = [seg.text for seg in audio.transcript[:3]]
            transcript_text = " ".join(segments)
            if len(transcript_text) > 300:
                transcript_text = transcript_text[:300] + "..."
        if audio.audio_meta.hls_url:
            stream_url = f"{settings.S3_ENDPOINT}/{settings.S3_BUCKET_NAME}/{audio.audio_meta.hls_url}"

    return PostResponse(
        id=str(post.id),
        title=post.title,
        duration=duration,
        file_size=file_size,
        record_date=post.record_date,
        upload_date=post.uploaded_date,
        mood=post.mood,
        album_id=post.album_id,
        hashtags=post.hashtags,
        text_content=transcript_text,
        thumbnail_url=post.thumbnail_url,
        stream_url=stream_url,
        attachedImageUrls=[]
    )