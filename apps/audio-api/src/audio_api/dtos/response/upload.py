from pydantic import Field

from audio_api.cores.model import CamelModel


class UploadInitResponse(CamelModel):
    job_id: str = Field(..., description="ID phiên làm việc, dùng để confirm sau này")
    file_name: str = Field(..., description="Tên file được tải lên")
    presigned_url: str = Field(..., description="URL để client PUT file trực tiếp lên S3")
    expires_in: int = 900