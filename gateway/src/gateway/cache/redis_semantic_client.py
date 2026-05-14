import redis


class RedisSemanticCacheClient:
    DEFAULT_TTL_SECONDS = 3600
    DEFAULT_SIMILARITY_THRESHOLD = 0.8
    DEFAULT_TOP_K = 3

    def __init__(
        self,
        redis_client: redis.Redis,
        default_ttl_seconds: int = DEFAULT_TTL_SECONDS,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        top_k: int = DEFAULT_TOP_K,
    ):
        self._redis = redis_client
        self._default_ttl_seconds = default_ttl_seconds
        self._similarity_threshold = similarity_threshold
        self._top_k = top_k

    def lookup(self, prompt: str, model: str, provider: str) -> str | None:
        raise NotImplementedError

    def store(self, prompt: str, response: str, model: str, provider: str) -> None:
        raise NotImplementedError
