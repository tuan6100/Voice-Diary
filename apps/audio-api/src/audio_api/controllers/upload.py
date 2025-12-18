from fastapi import APIRouter, Depends

from audio_api.cores.injectable import get_upload_service, get_current_user_id
from audio_api.schemas.upload_payload import UploadInitRequest, UploadInitResponse, UploadConfirmRequest
from audio_api.services.upload_flow import UploadFlowService

router = APIRouter()

@router.post("/init", response_model=UploadInitResponse)
async def init_upload(
        request: UploadInitRequest,
        user_id: str = Depends(get_current_user_id),
        service: UploadFlowService = Depends(get_upload_service)
):
    """
    Client gọi API này trước.
    Nhận về Presigned URL để upload trực tiếp lên S3.
    """
    result = await service.create_upload_session(
        user_id=user_id,
        filename=request.filename,
        content_type=request.content_type
    )
    return result

@router.post("/{job_id}/confirm")
async def confirm_upload(
        job_id: str,
        request: UploadConfirmRequest,
        user_id: str = Depends(get_current_user_id),
        service: UploadFlowService = Depends(get_upload_service)
):
    """
    Client gọi API này sau khi đã PUT file thành công lên S3.
    Server sẽ bắn Event để các worker bắt đầu xử lý.
    """
    result = await service.trigger_processing(user_id, job_id)
    return result