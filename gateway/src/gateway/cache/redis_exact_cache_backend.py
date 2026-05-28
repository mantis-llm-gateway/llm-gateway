import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class RedisExactCacheBackend:
    # TODO: observability (see TEA-87)

    def __init__(self, redis_client: Redis):
        self._redis = redis_client

    async def get(self, key: str) -> str | None:
        try:
            return await self._redis.get(key)
        except RedisError as e:
            logger.warning(
                "redis exact cache get failed: key=%s error_type=%s error=%s",
                key[:80],
                type(e).__name__,
                e,
            )
            return None

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            await self._redis.set(key, value, ex=ttl_seconds)
        except RedisError as e:
            logger.warning(
                "redis exact cache set failed: key=%s error_type=%s error=%s",
                key[:80],
                type(e).__name__,
                e,
            )
