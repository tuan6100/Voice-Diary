from datetime import datetime
from typing import Optional, List

from beanie import Indexed, Document
from pydantic import Field


class Post(Document):
    user_id: Indexed(str)
    audio_id: Indexed(str)
    album_id: Optional[str] = None
    title: str
    thumbnail_url: Optional[str] = None
    hashtags: List[str] = []
    views_count: int = 0
    record_date: Optional[datetime] = None
    uploaded_date: datetime = Field(default_factory=datetime.utcnow)
    mood: Optional[str] = None

    class Settings:
        name = "posts"
        indexes = [
            [("title", "text"), ("hashtags", "text")],
            "user_id",
            "uploaded_at"
        ]

# class Comment(Document):
#     user_id: str
#     post_id: str
#     content: str
#     created_at: datetime = Field(default_factory=datetime.utcnow)
#
#     class Settings:
#         name = "comments"