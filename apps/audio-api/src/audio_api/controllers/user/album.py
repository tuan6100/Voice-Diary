# src/audio_api/controllers/user/album.py
from fastapi import APIRouter, HTTPException
from beanie import PydanticObjectId
from audio_api.models.album import Album
from audio_api.models.post import Post
from audio_api.models.audio import Audio

router = APIRouter()


@router.post("/")
async def create_album(title: str, user_id: str = "test_user"):
    album = Album(user_id=user_id, title=title)
    await album.insert()
    return album


@router.post("/{album_id}/add")
async def add_post_to_album(album_id: PydanticObjectId, post_id: str):
    album = await Album.get(album_id)
    if not album: raise HTTPException(404)

    if post_id not in album.post_ids:
        album.post_ids.append(post_id)
        await album.save()
    return album


@router.get("/{album_id}/playlist")
async def get_playlist(album_id: PydanticObjectId):
    album = await Album.get(album_id)
    if not album: raise HTTPException(404)
    posts = await Post.find(Post.id << [PydanticObjectId(i) for i in album.post_ids]).to_list()

    tracks = []
    for p in posts:
        audio = await Audio.get(PydanticObjectId(p.audio_id))
        if audio and audio.audio_meta.hls_url:
            tracks.append({
                "title": p.caption,
                "file": audio.audio_meta.hls_url,
                "poster": "...",
                "howl": None,
                "meta": {
                    "postId": str(p.id),
                    "duration": audio.audio_meta.duration,
                    "artist": p.user_id
                }
            })

    return {
        "album": album.title,
        "tracks": tracks
    }