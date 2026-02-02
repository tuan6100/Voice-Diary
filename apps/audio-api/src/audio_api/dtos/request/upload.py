from pydantic import Field

from audio_api.cores.model import CamelModel


class UploadInitRequest(CamelModel):
    filename: str = Field(..., description="Tên file gốc, ví dụ: recording.mp3")
    content_type: str = Field(..., description="MIME type, ví dụ: audio/mpeg")
    file_size: int = Field(..., gt=0, description="Kích thước file (bytes)")

class UploadConfirmRequest(CamelModel):
    client_duration: float | None = None