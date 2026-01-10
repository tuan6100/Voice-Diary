# src/audio_api/controllers/user/post.py
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from beanie import PydanticObjectId
from beanie.operators import Text, RegEx

from audio_api.models.post import Post
from audio_api.models.audio import Audio, ProcessingStatus

router = APIRouter()


@router.get("/", response_model=List[dict])
async def get_feed(
        limit: int = 10,
        skip: int = 0,
        q: Optional[str] = None,
        hashtag: Optional[str] = None
):
    queries = []

    if q:
        queries.append(Text(q))

    if hashtag:
        queries.append(Post.hashtags == hashtag)
    query_obj = Post.find(*queries).sort(-Post.uploaded_at).limit(limit).skip(skip)
    posts = await query_obj.to_list()
    results = []
    for p in posts:
        audio = await Audio.get(PydanticObjectId(p.audio_id))
        if audio:
            results.append({
                "post": p,
                "audio_status": audio.status,
                "duration": audio.audio_meta.duration,
                "preview_text": audio.transcript[0].text if audio.transcript else ""
            })

    return results


@router.post("/{post_id}/like")
async def toggle_like(post_id: PydanticObjectId):
    post = await Post.get(post_id)
    if not post: raise HTTPException(404)
    await post.inc({Post.likes_count: 1})
    return {"likes": post.likes_count}


@router.post("/{post_id}/view")
async def increase_view(post_id: PydanticObjectId):
    post = await Post.get(post_id)
    if post:
        await post.inc({Post.views_count: 1})
    return {"status": "ok"}