import logging
from typing import Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Depends, Query

from audio_api.cores.injectable import get_current_user_id
from audio_api.dtos.request.album import CreateAlbumRequest, RenameAlbumRequest, AddPostToAlbumRequest
from audio_api.dtos.response.album import (
    AlbumMessageResponse,
    AlbumPlaylistResponse,
    AlbumShuffleResponse,
    build_album_playlist_response,
    build_album_shuffle_response, AlbumResponse, build_album_response,
)
from audio_api.models.album import Album
from audio_api.models.post import Post

router = APIRouter()


@router.post("/", summary="1. Tạo album mới", response_model=AlbumResponse)
async def create_album(
        request: CreateAlbumRequest,
        user_id: str = Depends(get_current_user_id)
):
    album = Album(user_id=user_id, title=request.title)
    await album.insert()
    return build_album_response(album)


@router.get("/my", summary="2. Lấy danh sách album của tôi", response_model=list[AlbumResponse])
async def get_my_albums(
        user_id: str = Depends(get_current_user_id)
):
    albums = await Album.find(Album.user_id == user_id).to_list()
    return [build_album_response(album) for album in albums]


@router.get("/search", summary="3. Tìm kiếm album", response_model=list[AlbumResponse])
async def search_albums(
        keyword: Optional[str] = Query(None, min_length=1),
        limit: int = 10
):
    if keyword:
        albums = await Album.find({"title": {"$regex": keyword, "$options": "i"}}).limit(limit).to_list()
    else:
        albums = await Album.find_all().sort("-id").limit(limit).to_list()
    return [build_album_response(album) for album in albums]


@router.get("/{album_id}", summary="4. Xem chi tiết album", response_model=AlbumResponse)
async def get_album_detail(album_id: PydanticObjectId):
    album = await Album.get(album_id)
    if not album:
        raise HTTPException(404, "Album not found")
    return build_album_response(album)


@router.patch("/{album_id}", summary="5. Đổi tên album", response_model=AlbumResponse)
async def update_album(
        album_id: PydanticObjectId,
        request: RenameAlbumRequest,
        user_id: str = Depends(get_current_user_id)
):
    album = await Album.get(album_id)
    if not album:
        raise HTTPException(404, "Album not found")
    if album.user_id != user_id:
        raise HTTPException(403, "You do not have permission to modify this album")

    album.title = request.title
    await album.save()
    return build_album_response(album)


@router.delete("/{album_id}", summary="6. Xóa album", response_model=AlbumMessageResponse)
async def delete_album(
        album_id: PydanticObjectId,
        user_id: str = Depends(get_current_user_id)
):
    album = await Album.get(album_id)
    if not album:
        raise HTTPException(404, "Album not found")
    if album.user_id != user_id:
        raise HTTPException(403, "You do not have permission to delete this album")
    await album.delete()
    return AlbumMessageResponse(message="Album deleted successfully")


@router.post("/{album_id}/posts", summary="7. Thêm bài hát vào album")
async def add_post_to_album(
        album_id: PydanticObjectId,
        request: AddPostToAlbumRequest,
        user_id: str = Depends(get_current_user_id)
):
    album = await Album.get(album_id)
    if not album:
        raise HTTPException(404, "Album not found")
    if album.user_id != user_id:
        raise HTTPException(403, "You do not have permission to modify this album")

    post = await Post.get(PydanticObjectId(request.post_id))
    if not post:
        raise HTTPException(404, "Post not found")

    if request.post_id not in album.post_ids:
        album.post_ids.append(request.post_id)
        await album.save()

    return build_album_response(album)


@router.delete("/{album_id}/posts/{post_id}", summary="8. Xóa bài hát khỏi album")
async def remove_post_from_album(
        album_id: PydanticObjectId,
        post_id: str,
        user_id: str = Depends(get_current_user_id)
):
    album = await Album.get(album_id)
    if not album:
        raise HTTPException(404, "Album not found")
    if album.user_id != user_id:
        raise HTTPException(403, "You do not have permission to modify this album")
    if post_id in album.post_ids:
        album.post_ids.remove(post_id)
        await album.save()
    else:
        raise HTTPException(404, "Post not in this album")
    return build_album_response(album)


@router.get("/{album_id}/playlist", summary="9. Lấy Playlist phát nhạc", response_model=AlbumPlaylistResponse)
async def get_playlist(album_id: PydanticObjectId):
    album = await Album.get(album_id)
    if not album:
        raise HTTPException(404, "Album not found")

    return await build_album_playlist_response(album)


@router.get("/{album_id}/shuffle", summary="10. Phát ngẫu nhiên (Shuffle)", response_model=AlbumShuffleResponse)
async def get_shuffled_playlist(album_id: PydanticObjectId):
    album = await Album.get(album_id)
    if not album:
        raise HTTPException(404, "Album not found")

    return await build_album_shuffle_response(album)