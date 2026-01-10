from pydantic.v1 import BaseModel


class CreatePostRequest(BaseModel):
    user_id: str
    caption: str = None
    hashtags: list[str] = []
