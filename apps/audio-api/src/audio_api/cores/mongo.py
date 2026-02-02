from beanie import init_beanie
from pymongo import AsyncMongoClient

from audio_api.cores.config import settings
from audio_api.models.album import Album
from audio_api.models.audio import Audio
from audio_api.models.post import Post
from audio_api.models.user import User


async def init_db():
    client = AsyncMongoClient(settings.MONGODB_URL)

    await init_beanie(
        database=client[settings.DATABASE_NAME],
        document_models=[
            User,
            Audio,
            Post,
            Album
        ]
    )