from fastapi import APIRouter, HTTPException
from typing import List
from beanie import PydanticObjectId
from pydantic import BaseModel

from user_api.models.album import Album
from user_api.models.post import Post

router = APIRouter()


class AlbumCreate(BaseModel):
    title: str
    description: str = None


class AddPostToAlbum(BaseModel):
    post_id: str


@router.post("/")
async def create_album(payload: AlbumCreate, user_id: str = "user_test_id"):
    album = Album(user_id=user_id, **payload.model_dump())
    await album.insert()
    return album


@router.post("/{album_id}/posts")
async def add_post_to_album(album_id: PydanticObjectId, payload: AddPostToAlbum):
    album = await Album.get(album_id)
    if not album:
        raise HTTPException(404, "Album not found")


    post = await Post.get(PydanticObjectId(payload.post_id))
    if not post:
        raise HTTPException(404, "Post not found")


    if str(post.id) not in album.post_ids:
        album.post_ids.append(str(post.id))
        await album.save()

    return {"status": "added", "album": album}