import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class RedisExactCacheBackend:
    # TODO: error handling. Decide policy (swallow + log vs. raise) and wire logging.

    def __init__(self, redis_client: Redis):
        self._redis = redis_client

    async def get(self, key: str) -> str | None:
        result = await self._redis.get(key)

        if result:
            logger.info("exact cache hit", extra={"key": key})
        else:
            logger.info("exact cache lookup miss")

        return result

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:

        await self._redis.set(key, value, ex=ttl_seconds)

        logger.info(
            "set key in exact cache",
            extra={"key": key, "cached response": value, "ttl": ttl_seconds},
        )
