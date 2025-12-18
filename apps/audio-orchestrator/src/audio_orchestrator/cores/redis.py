from redis.asyncio import Redis

from audio_orchestrator.cores.config import settings


async def get_redis_client() -> Redis:

    return Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        encoding="utf-8"
    )