from typing import List, Optional
from datetime import datetime
from beanie import Document, Indexed
from pydantic import Field


class Album(Document):
    user_id: Indexed(str)
    title: str
    description: Optional[str] = None
    cover_url: Optional[str] = None
    post_ids: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "albums"