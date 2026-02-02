from typing import Optional, List

from pydantic import Field

from audio_api.cores.model import CamelModel


class UploadInitRequest(CamelModel):
    filename: str = Field(..., description="Tên file gốc, ví dụ: recording.mp3")
    content_type: str = Field(..., description="MIME type, ví dụ: audio/mpeg")

class UploadConfirmRequest(CamelModel):
    job_id: str = Field(..., description="ID của job upload")
    title: Optional[str] = Field("Untitled", description="Tiêu đề của audio sau khi upload")
    duration: float = 0.0
    file_size: int = 0