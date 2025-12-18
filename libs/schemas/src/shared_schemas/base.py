from pydantic import BaseModel

class SpeakerSegment(BaseModel):
    """Định nghĩa một lượt nói của người dùng"""
    speaker: str
    start: float
    end: float