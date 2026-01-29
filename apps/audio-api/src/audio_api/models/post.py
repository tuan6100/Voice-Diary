from datetime import datetime
from typing import Optional, List

from beanie import Indexed, Document
from pydantic import Field


class Post(Document):
    user_id: Indexed(str)
    audio_id: Indexed(str)
    caption: Optional[str] = None
    background: Optional[str] = None
    hashtags: List[str] = []
    likes_count: int = 0
    views_count: int = 0
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "posts"
        indexes = [
            [("caption", "text"), ("hashtags", "text")],
            "user_id",
            "uploaded_at"
        ]

class Comment(Document):
    user_id: str
    post_id: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "comments"