from typing import List, Optional
from datetime import datetime
from enum import Enum
from beanie import Document, Indexed
from pydantic import BaseModel, Field


class ProcessingStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class AudioMetadata(BaseModel):
    original_url: Optional[str] = None
    hls_url: Optional[str] = None
    duration: float = 0.0
    file_size: int = 0


class Post(Document):
    user_id: Indexed(str)
    caption: Optional[str] = None
    hashtags: List[str] = []


    status: ProcessingStatus = ProcessingStatus.PENDING
    job_id: Optional[str] = Indexed(unique=True)
    audio_meta: AudioMetadata = AudioMetadata()


    transcript: List[TranscriptSegment] = []


    likes_count: int = 0
    views_count: int = 0

    created_at: datetime = Field(default_factory=datetime.utcnow)
    recorded_date: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "posts"
        indexes = [
            [("transcript.text", "text"), ("caption", "text")],
            "hashtags",
            "created_at"
        ]