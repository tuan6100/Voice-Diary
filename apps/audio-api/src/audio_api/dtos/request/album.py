from pydantic import Field

from audio_api.cores.model import CamelModel


class CreateAlbumRequest(CamelModel):
    title: str = Field(..., min_length=1, max_length=200)


class RenameAlbumRequest(CamelModel):
    title: str = Field(..., min_length=1, max_length=200)


class AddPostToAlbumRequest(CamelModel):
    post_id: str = Field(..., min_length=1)
