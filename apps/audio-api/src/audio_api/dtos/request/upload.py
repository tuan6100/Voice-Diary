from pydantic import BaseModel, Field


class UploadInitRequest(BaseModel):
    filename: str = Field(..., description="Tên file gốc, ví dụ: recording.mp3")
    content_type: str = Field(..., description="MIME type, ví dụ: audio/mpeg")
    file_size: int = Field(..., gt=0, description="Kích thước file (bytes)")

class UploadConfirmRequest(BaseModel):
    client_duration: float | None = None