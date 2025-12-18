from fastapi import APIRouter

from user_api.controller import post, album

api_router = APIRouter()



api_router.include_router(post.router, prefix="/posts", tags=["Posts"])
api_router.include_router(album.router, prefix="/albums", tags=["Albums"])