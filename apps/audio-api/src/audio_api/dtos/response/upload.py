from pydantic import Field
from pydantic.v1 import BaseModel


class UploadInitResponse(BaseModel):
    job_id: str = Field(..., description="ID phiên làm việc, dùng để confirm sau này")
    presigned_url: str = Field(..., description="URL để client PUT file trực tiếp lên S3")
    expires_in: int = 900