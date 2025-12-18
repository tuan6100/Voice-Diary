import datetime

from fastapi import APIRouter, HTTPException, Query
from typing import List
from beanie import PydanticObjectId

from user_api.models.post import Post, ProcessingStatus
from user_api.schemas.post import PostResponse, PostCreateRequest, PostUpdateRequest

router = APIRouter()


@router.get("/", response_model=List[PostResponse])
async def get_feed(limit: int = 10, skip: int = 0):
    posts = await Post.find(
        Post.status == ProcessingStatus.COMPLETED
    ).sort(-Post.created_at).limit(limit).skip(skip).to_list()
    return posts


@router.post("/", response_model=PostResponse)
async def create_post(payload: PostCreateRequest, user_id: str = "user_test_id"):
    post = Post(
        user_id=user_id,
        caption=payload.caption,
        hashtags=payload.hashtags,
        recorded_date=payload.recorded_date or datetime.utcnow()
    )
    await post.insert()
    return post



@router.get("/{post_id}", response_model=PostResponse)
async def get_post_detail(post_id: PydanticObjectId):
    post = await Post.get(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.patch("/{post_id}/internal/status")
async def update_post_status(post_id: PydanticObjectId, payload: PostUpdateRequest):
    post = await Post.get(post_id)
    if not post:
        raise HTTPException(status_code=404)
    update_data = payload.model_dump(exclude_unset=True)
    await post.set(update_data)
    return {"status": "updated"}