from fastapi import APIRouter, Depends

from audio_api.cores.injectable import get_current_user_id

router = APIRouter()


