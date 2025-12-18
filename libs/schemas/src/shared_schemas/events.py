from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from shared_schemas.base import SpeakerSegment


class FileUploadedEvent(BaseModel):
    job_id: str
    user_id: str
    storage_path: str


class PreprocessCompletedEvent(BaseModel):
    job_id: str
    clean_audio_path: str


class SegmentCompletedEvent(BaseModel):
    job_id: str
    audio_path: str
    segments: List[Dict[str, Any]]

class EnhancementCompletedEvent(BaseModel):
    job_id: str
    index: int
    s3_path: str
    snr: float
    is_denoised: bool
    start_ms: int
    end_ms: int

class DiarizationCompletedEvent(BaseModel):
    job_id: str
    speaker_segments: List[SpeakerSegment]

class RecognitionCompletedEvent(BaseModel):
    job_id: str
    index: int
    text: str
    confidence: float
    start_ms: int
    end_ms: int
    transcript_s3_path: Optional[str] = None

class TranscodeCompletedEvent(BaseModel):
    job_id: str
    hls_path: str


class JobCompletedEvent(BaseModel):
    """Sự kiện thông báo Job đã hoàn tất sau Post-processor"""
    job_id: str
    metadata_path: str
    status: str  # e.g., "COMPLETED"; keep as string for now per conventions
    error: Optional[str] = None  # optional error message when failures occur
