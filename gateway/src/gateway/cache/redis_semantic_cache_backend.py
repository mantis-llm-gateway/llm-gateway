import redis


class RedisSemanticCacheBackend:
    # TODO: make configurable from env variables (local) or config file (production)
    DEFAULT_TTL_SECONDS = 3600
    DEFAULT_SIMILARITY_THRESHOLD = 0.8
    DEFAULT_TOP_K = 3

    PREFIX = "prompt:semantic:"

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
        # create embedding of prompt
        # search redis for similar vectors filtered on model and provider
        # given top-k, return the first one (maybe log the others for threshold tuning?)
        raise NotImplementedError

    def store(self, prompt: str, response: str, model: str, provider: str) -> None:
        # get embedding
        # generate a uuid (this will be a part of the key -> prompt:semmantic:<uuid>)
        # build key
        # store in redis as a hash with the response, (model and provider as metadata fields)
        # set the ttl
        # return success message (the uuid of the key or something)
        raise NotImplementedError
