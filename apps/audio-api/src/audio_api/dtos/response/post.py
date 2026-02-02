from datetime import datetime
from typing import List, Optional

from pydantic import Field

from audio_api.cores.model import CamelModel
from audio_api.models.audio import Audio
from audio_api.models.post import Post


class PostResponse(CamelModel):
    id: str
    title: str
    mp3_path: Optional[str] = ""
    duration: float = 0.0
    file_size: int = 0
    record_date: Optional[datetime] = None
    upload_date: Optional[datetime] = None
    mood: Optional[str] = "neutral"
    album_id: Optional[str] = None
    hashtags: List[str] = []
    text_content: str = ""  # Short transcript
    thumbnail_url: Optional[str] = ""


class ToggleLikeResponse(CamelModel):
    likes: int = Field(..., ge=0)


class IncreaseViewResponse(CamelModel):
    status: str


def build_post_response(post: Post, audio: Optional[Audio]) -> PostResponse:
    mp3_path = ""
    duration = 0.0
    transcript_text = ""
    file_size = 0

    if audio:
        if audio.audio_meta:
            mp3_path = audio.audio_meta.hls_url or ""
            duration = audio.audio_meta.duration or 0.0
            file_size = getattr(audio.audio_meta, "size", 0)

        if audio.transcript:
            segments = [seg.text for seg in audio.transcript[:3]]
            transcript_text = " ".join(segments)
            if len(transcript_text) > 300:
                transcript_text = transcript_text[:300] + "..."

    if not transcript_text and post.text_content:
        transcript_text = post.text_content

    return PostResponse(
        id=str(post.id),
        title=post.title,
        mp3_path=mp3_path,
        duration=duration,
        file_size=file_size,
        record_date=post.record_date,
        upload_date=post.uploaded_at,
        mood=post.mood,
        album_id=post.album_id,
        hashtags=post.hashtags,
        text_content=transcript_text,
        thumbnail_url=post.thumbnail_url
    )