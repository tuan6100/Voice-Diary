from pydantic import BaseModel
from typing import Optional, List, Dict


class PreprocessCommand(BaseModel):
    job_id: str
    input_path: str


class SegmentCommand(BaseModel):
    job_id: str
    input_path: str

class EnhanceCommand(BaseModel):
    job_id: str
    index: int
    s3_path: str
    start_ms: int
    end_ms: int

class DiarizeCommand(BaseModel):
    job_id: str
    input_path: str

class RecognizeCommand(BaseModel):
    job_id: str
    input_path: str
    segments: Optional[List[Dict]] = None
    index: Optional[int] = None
    start_ms: int
    end_ms: int

class TranscodeCommand(BaseModel):
    job_id: str
    input_path: str

class PostProcessCommand(BaseModel):
    job_id: str