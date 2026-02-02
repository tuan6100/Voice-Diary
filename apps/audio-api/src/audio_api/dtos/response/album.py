import random
from datetime import datetime
from typing import List, Optional

from beanie import PydanticObjectId
from beanie.operators import In
from pydantic import Field

from audio_api.cores.model import CamelModel
from audio_api.models.album import Album
from audio_api.models.audio import Audio
from audio_api.models.post import Post


# --- Main DTO cho Album (Khớp với Flutter Album Model) ---
class AlbumResponse(CamelModel):
    id: str
    name: str = Field(..., description="Map từ title của Album")
    description: Optional[str] = ""
    cover_url: Optional[str] = ""
    post_count: int = 0
    created_at: Optional[datetime] = None

# --- Các DTO cũ giữ nguyên cho Player ---
class AlbumMessageResponse(CamelModel):
    message: str

class PlaylistTrackMetaDTO(CamelModel):
    post_id: str = Field(..., alias="postId")
    audio_id: str = Field(..., alias="audioId")
    duration: Optional[float] = None
    artist: str

class PlaylistTrackDTO(CamelModel):
    title: str
    file: str
    poster: str
    howl: Optional[dict] = None
    meta: PlaylistTrackMetaDTO

class AlbumPlaylistResponse(CamelModel):
    id: str
    album: str
    tracks: List[PlaylistTrackDTO]
    total_duration: float = 0

class AlbumShuffleResponse(CamelModel):
    id: str
    album: str
    mode: str = "shuffle"
    tracks: List[PlaylistTrackDTO]


# --- Helper Builder Function ---
def build_album_response(album: Album) -> AlbumResponse:
    return AlbumResponse(
        id=str(album.id),
        name=album.title,
        description=album.description,
        cover_url=album.cover_url,
        post_count=len(album.post_ids or []),
        created_at=album.created_at
    )

async def build_track_list(post_ids: List[str]) -> List[PlaylistTrackDTO]:
    if not post_ids:
        return []

    obj_ids = [PydanticObjectId(i) for i in post_ids]
    posts = await Post.find(In(Post.id, obj_ids)).to_list()
    post_map = {str(p.id): p for p in posts}
    # Giữ đúng thứ tự trong mảng post_ids
    ordered_posts = [post_map[pid] for pid in post_ids if pid in post_map]

    tracks: List[PlaylistTrackDTO] = []
    for p in ordered_posts:
        if not p.audio_id:
            continue
        audio = await Audio.get(PydanticObjectId(p.audio_id))
        if not (audio and audio.audio_meta and audio.audio_meta.hls_url):
            continue

        tracks.append(
            PlaylistTrackDTO(
                title=p.title or "Untitled",
                file=audio.audio_meta.hls_url,
                poster=p.thumbnail_url or "https://via.placeholder.com/150",
                howl=None,
                meta=PlaylistTrackMetaDTO(
                    postId=str(p.id),
                    audioId=str(audio.id),
                    duration=audio.audio_meta.duration,
                    artist=p.user_id,
                ),
            )
        )
    return tracks

async def build_album_playlist_response(album: Album) -> AlbumPlaylistResponse:
    tracks = await build_track_list(list(album.post_ids or []))
    total_duration = sum([(t.meta.duration or 0) for t in tracks])
    return AlbumPlaylistResponse(
        id=str(album.id),
        album=album.title,
        tracks=tracks,
        total_duration=total_duration,
    )

async def build_album_shuffle_response(album: Album) -> AlbumShuffleResponse:
    shuffled_ids = list(album.post_ids or [])
    random.shuffle(shuffled_ids)
    tracks = await build_track_list(shuffled_ids)
    return AlbumShuffleResponse(
        id=str(album.id),
        album=album.title,
        mode="shuffle",
        tracks=tracks,
    )