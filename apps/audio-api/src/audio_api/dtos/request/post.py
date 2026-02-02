from datetime import datetime
from typing import Optional, List

from audio_api.cores.model import CamelModel


class CreatePostRequest(CamelModel):
    user_id: str
    caption: str = None
    hashtags: list[str] = []

class SearchFilter(CamelModel):
    min_duration: int = 0
    max_duration: int = 3600
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    sort_by: str = "newest"

class UpdatePostRequest(CamelModel):
    title: str
    text_content: str
    mood: Optional[str] = None
    hashtags: List[str] = []


