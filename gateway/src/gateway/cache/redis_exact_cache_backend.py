from redis.asyncio import Redis


class RedisExactCacheBackend:
    # TODO: error handling. Decide policy (swallow + log vs. raise) and wire logging.

    def __init__(self, redis_client: Redis):
        self._redis = redis_client

    async def get(self, key: str) -> str | None:
        return await self._redis.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        print("We're trying to store (`.set`) in the  exact-match cache now...")

        await self._redis.set(key, value, ex=ttl_seconds)
        print(f"Attempting to store key {key[:25]}... with TTL of {ttl_seconds} seconds")
