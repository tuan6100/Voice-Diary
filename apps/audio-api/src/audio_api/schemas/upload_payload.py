from pydantic import BaseModel, Field

class UploadInitRequest(BaseModel):
    filename: str = Field(..., description="Tên file gốc, ví dụ: recording.mp3")
    content_type: str = Field(..., description="MIME type, ví dụ: audio/mpeg")
    file_size: int = Field(..., gt=0, description="Kích thước file (bytes)")

class UploadInitResponse(BaseModel):
    job_id: str = Field(..., description="ID phiên làm việc, dùng để confirm sau này")
    presigned_url: str = Field(..., description="URL để client PUT file trực tiếp lên S3")
    expires_in: int = 900

class UploadConfirmRequest(BaseModel):

    client_duration: float | None = None