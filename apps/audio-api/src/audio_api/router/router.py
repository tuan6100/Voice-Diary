from fastapi import APIRouter
from audio_api.controllers.audio import upload, media
from audio_api.controllers.user import post, album, auth, profile

api_router = APIRouter()

api_router.include_router(upload.router, prefix="/upload", tags=["Upload"])
api_router.include_router(media.router, prefix="/media", tags=["Streaming"])

api_router.include_router(post.router, prefix="/posts", tags=["Feed & Posts"])
api_router.include_router(album.router, prefix="/albums", tags=["Albums"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])