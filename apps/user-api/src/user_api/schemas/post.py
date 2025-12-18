from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from user_api.models.post import ProcessingStatus, AudioMetadata, TranscriptSegment



class PostCreateRequest(BaseModel):
    caption: Optional[str] = None
    hashtags: List[str] = []
    recorded_date: Optional[datetime] = None


class PostUpdateRequest(BaseModel):
    status: Optional[ProcessingStatus] = None
    audio_meta: Optional[AudioMetadata] = None
    transcript: Optional[List[TranscriptSegment]] = None


class PostResponse(BaseModel):
    id: str
    user_id: str
    caption: Optional[str]
    status: ProcessingStatus
    audio_meta: AudioMetadata
    transcript: List[TranscriptSegment]
    created_at: datetime
    likes_count: int