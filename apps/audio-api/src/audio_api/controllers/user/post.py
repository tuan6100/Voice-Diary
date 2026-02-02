from typing import List, Optional

from beanie import PydanticObjectId
from beanie.operators import Text
from fastapi import APIRouter, HTTPException, Response

from audio_api.dtos.response.post import (
    ToggleLikeResponse,
    IncreaseViewResponse, PostResponse, build_post_response,
)
from audio_api.models.audio import Audio
from audio_api.models.post import Post
from typing import List, Optional, Literal

router = APIRouter()

@router.get("/", response_model=List[PostResponse])
async def get_feed(
        limit: int = 10,
        skip: int = 0,
        q: Optional[str] = None,
        hashtag: Optional[str] = None,
        sort_by: Literal["newest", "popular"] = "newest"
):
    queries = []
    if q:
        queries.append(Text(q))
    if hashtag:
        queries.append(Post.hashtags == hashtag)
    sort_criteria = -Post.uploaded_date
    if sort_by == "popular":
        sort_criteria = -Post.views_count
    query_obj = Post.find(*queries).sort(sort_criteria).limit(limit).skip(skip)
    posts = await query_obj.to_list()
    if not posts:
        return Response(status_code=204)
    results = []
    for post in posts:
        audio = None
        if post.audio_id:
            audio = await Audio.get(PydanticObjectId(post.audio_id))
        results.append(build_post_response(post, audio))
    return results


@router.post("/{post_id}/like", response_model=ToggleLikeResponse)
async def toggle_like(post_id: PydanticObjectId):
    post = await Post.get(post_id)
    if not post:
        raise HTTPException(404)
    await post.inc({Post.likes_count: 1})
    return ToggleLikeResponse(likes=post.likes_count)


@router.post("/{post_id}/view", response_model=IncreaseViewResponse)
async def increase_view(post_id: PydanticObjectId):
    post = await Post.get(post_id)
    if post:
        await post.inc({Post.views_count: 1})
    return IncreaseViewResponse(status="ok")
