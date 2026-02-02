from typing import Optional
from datetime import datetime
from beanie import Document, Indexed
from pydantic import Field

from audio_api.utils.password_encryption import hash_password


class User(Document):
    username: Indexed(str, unique=True)
    email: Indexed(str, unique=True)
    password_hash: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"