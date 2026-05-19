from typing import cast

import redis


class RedisExactCacheBackend:
    # TODO: error handling. Decide policy (swallow + log vs. raise) and wire logging.

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    def get(self, key: str) -> str | None:
        value = cast(bytes | None, self._redis.get(key))
        return value.decode("utf-8") if value is not None else None

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        print("We're trying to store (`.set`) in the  exact-match cache now...")

        self._redis.set(key, value, ex=ttl_seconds)
        print(f"Attempting to store key {key[:25]}... with TTL of {ttl_seconds} seconds")
