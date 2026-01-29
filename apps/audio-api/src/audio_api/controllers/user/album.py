import random
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from beanie import PydanticObjectId
from beanie.operators import In

from audio_api.cores.injectable import get_current_user_id
from audio_api.models.album import Album
from audio_api.models.post import Post
from audio_api.models.audio import Audio

router = APIRouter()

@router.post("/", summary="1. Tạo album mới")
async def create_album(
        title: str,
        user_id: str = Depends(get_current_user_id)
):
    album = Album(user_id=user_id, title=title, post_ids=[])
    await album.insert()
    return album


@router.get("/my", summary="2. Lấy danh sách album của tôi")
async def get_my_albums(
        user_id: str = Depends(get_current_user_id)
):
    albums = await Album.find(Album.user_id == user_id).to_list()
    return albums


@router.get("/search", summary="3. Tìm kiếm album")
async def search_albums(
        keyword: Optional[str] = Query(None, min_length=1),
        limit: int = 10
):
    if keyword:
        albums = await Album.find({"title": {"$regex": keyword, "$options": "i"}}).limit(limit).to_list()
    else:
        albums = await Album.find_all().sort("-id").limit(limit).to_list()
    return albums


@router.get("/{album_id}", summary="4. Xem chi tiết album")
async def get_album_detail(album_id: PydanticObjectId):
    album = await Album.get(album_id)
    if not album:
        raise HTTPException(404, "Album not found")
    return {
        **album.model_dump(),
        "total_tracks": len(album.post_ids)
    }


@router.patch("/{album_id}", summary="5. Đổi tên album")
async def update_album(
        album_id: PydanticObjectId,
        title: str,
        user_id: str = Depends(get_current_user_id)
):
    album = await Album.get(album_id)
    if not album:
        raise HTTPException(404, "Album not found")
    if album.user_id != user_id:
        raise HTTPException(403, "You do not have permission to modify this album")

    album.title = title
    await album.save()
    return album


@router.delete("/{album_id}", summary="6. Xóa album")
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
    return {"message": "Album deleted successfully"}


@router.post("/{album_id}/posts", summary="7. Thêm bài hát vào album")
async def add_post_to_album(
        album_id: PydanticObjectId,
        post_id: str,
        user_id: str = Depends(get_current_user_id)
):
    album = await Album.get(album_id)
    if not album:
        raise HTTPException(404, "Album not found")
    if album.user_id != user_id:
        raise HTTPException(403, "You do not have permission to modify this album")
    post = await Post.get(PydanticObjectId(post_id))
    if not post:
        raise HTTPException(404, "Post not found")
    if post_id not in album.post_ids:
        album.post_ids.append(post_id)
        await album.save()

    return album


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
    return album



async def _build_track_list(post_ids: List[str]):
    if not post_ids:
        return []
    obj_ids = [PydanticObjectId(i) for i in post_ids]
    posts = await Post.find(In(Post.id, obj_ids)).to_list()
    post_map = {str(p.id): p for p in posts}
    ordered_posts = [post_map[pid] for pid in post_ids if pid in post_map]
    tracks = []
    for p in ordered_posts:
        if not p.audio_id:
            continue
        audio = await Audio.get(PydanticObjectId(p.audio_id))
        if audio and audio.audio_meta and audio.audio_meta.hls_url:
            tracks.append({
                "title": p.caption or "Untitled",
                "file": audio.audio_meta.hls_url,
                "poster": "https://via.placeholder.com/150",
                "howl": None,
                "meta": {
                    "postId": str(p.id),
                    "audioId": str(audio.id),
                    "duration": audio.audio_meta.duration,
                    "artist": p.user_id
                }
            })
    return tracks


@router.get("/{album_id}/playlist", summary="9. Lấy Playlist phát nhạc")
async def get_playlist(album_id: PydanticObjectId):
    album = await Album.get(album_id)
    if not album:
        raise HTTPException(404, "Album not found")
    tracks = await _build_track_list(album.post_ids)
    return {
        "id": str(album.id),
        "album": album.title,
        "tracks": tracks,
        "total_duration": sum([t['meta']['duration'] for t in tracks if t['meta']['duration']])
    }


@router.get("/{album_id}/shuffle", summary="10. Phát ngẫu nhiên (Shuffle)")
async def get_shuffled_playlist(album_id: PydanticObjectId):
    album = await Album.get(album_id)
    if not album:
        raise HTTPException(404, "Album not found")
    shuffled_ids = list(album.post_ids)
    random.shuffle(shuffled_ids)
    tracks = await _build_track_list(shuffled_ids)
    return {
        "id": str(album.id),
        "album": album.title,
        "mode": "shuffle",
        "tracks": tracks
    }