from redis.asyncio import ConnectionPool
from redis.asyncio.client import Redis

from audio_api.cores.config import settings



pool = ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)

def get_redis_client() -> Redis:
    return Redis(connection_pool=pool)