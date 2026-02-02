import logging
from typing import List, Optional

from beanie import PydanticObjectId
from beanie.operators import Text
from fastapi import APIRouter, HTTPException, Response, Depends

from audio_api.cores.injectable import get_current_user_id
from audio_api.dtos.request.post import UpdatePostRequest
from audio_api.dtos.response.post import (
    ToggleLikeResponse,
    IncreaseViewResponse, PostResponse, build_post_response,
)
from audio_api.models.audio import Audio
from audio_api.models.post import Post
from typing import List, Optional, Literal

from audio_api.utils.transcript_parser import parse_transcript_from_text

router = APIRouter()

@router.get("/", response_model=List[PostResponse])
async def get_feed(
        limit: int = 10,
        skip: int = 0,
        q: Optional[str] = None,
        hashtag: Optional[str] = None,
        sort_by: Literal["newest", "popular"] = "newest",
        user_id: str = Depends(get_current_user_id)
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


@router.get("/{post_id}", response_model=PostResponse)
async def get_post_detail(post_id: PydanticObjectId, user_id: str = Depends(get_current_user_id)):
    logging.info("Requesting post detail for post_id: %s by user_id: %s", post_id, user_id)
    post = await Post.get(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    if str(post.user_id) != user_id:
        raise HTTPException(403, "Access denied")
    audio = None
    if post.audio_id:
        audio = await Audio.get(PydanticObjectId(post.audio_id))
    return build_post_response(post, audio, is_detail=True)

@router.put("/{post_id}", response_model=PostResponse)
async def update_post(
        post_id: PydanticObjectId,
        body: UpdatePostRequest,
        user_id: str = Depends(get_current_user_id)
):
    post = await Post.get(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    if str(post.user_id) != user_id:
        raise HTTPException(403, "Not authorized")
    post.title = body.title
    post.mood = body.mood
    post.hashtags = body.hashtags
    await post.save()
    audio = None
    if post.audio_id:
        audio = await Audio.get(PydanticObjectId(post.audio_id))
        if audio:
            if body.text_content:
                new_segments = parse_transcript_from_text(body.text_content)
                if new_segments:
                    audio.transcript = new_segments
            audio.caption = body.title
            await audio.save()
    return build_post_response(post, audio, is_detail=True)
