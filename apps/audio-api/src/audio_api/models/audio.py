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
    CANCELLED = "CANCELLED"

class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str

class AudioMetadata(BaseModel):
    original_url: Optional[str] = None
    hls_url: Optional[str] = None
    duration: float = 0.0
    file_size: int = 0
    google_doc_id: Optional[str] = None


class Audio(Document):
    user_id: Indexed(str)
    status: ProcessingStatus = ProcessingStatus.PENDING
    job_id: Optional[str] = Indexed(unique=True)
    audio_meta: AudioMetadata = AudioMetadata()
    transcript: List[TranscriptSegment] = []
    caption: str = ""
    created_at: datetime

    class Settings:
        name = "audios"
        indexes = [
            [("transcript.text", "text")],
            "hashtags",
            "created_at"
        ]