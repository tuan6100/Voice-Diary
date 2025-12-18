from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from user_api.cores.config import settings
from user_api.models.album import Album
from user_api.models.post import Post
from user_api.models.user import User


async def init_db():
    client = AsyncIOMotorClient(settings.MONGODB_URL)


    await init_beanie(
        database=client[settings.DATABASE_NAME],
        document_models=[
            User,
            Post,
            Album
        ]
    )