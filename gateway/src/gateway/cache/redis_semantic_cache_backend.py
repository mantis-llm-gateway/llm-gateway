import uuid
from typing import Protocol

import redis


class Embedder(Protocol):
    """
    Interface for embedding text. Should return a list of floats
    """

    def embed(self, text: str) -> list[float]: ...


class BedrockEmbedder:
    """
    TODO: add descriptive and succinct docstring
    """

    # Our chosen prompt embedding model
    DEFAULT_EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"

    def __init__(self, bedrock_client, model: str = DEFAULT_EMBEDDING_MODEL):
        self._bedrock_client = bedrock_client
        self._model = model

    def embed(self, text: str) -> list[float]:
        # invoke the model
        # return the embedding
        raise NotImplementedError


class RedisSemanticCacheBackend:
    # TODO: make configurable from env variables (local) or config file (production)
    # TODO: verify FT.SEARCH syntax against ElastiCache w/ Valkey before prod deploy
    DEFAULT_TTL_SECONDS = 3600
    DEFAULT_SIMILARITY_THRESHOLD = 0.8
    DEFAULT_TOP_K = 3

    PREFIX = "prompt:semantic:"

    def __init__(
        self,
        redis_client: redis.Redis,
        embedder: Embedder,
        default_ttl_seconds: int = DEFAULT_TTL_SECONDS,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        top_k: int = DEFAULT_TOP_K,
    ):
        self._redis = redis_client
        self._embedder = embedder
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
        embedding = self._embedder.embed(prompt)
        # generate a uuid (this will be a part of the key -> prompt:semantic:<uuid>)
        key_id = uuid.uuid4().hex
        # build key
        key = f"{self.PREFIX}{key_id}"
        # store prompt, response, embedding (redis HASH?) (model and provider as metadata fields)
        # Stored as a Redis HASH so vector + response + tags stay co-located.
        self._redis.hset(
            key,
            mapping={
                "vector": self._encode_vector(embedding),
                "payload": response,
                "model": model,
                "provider": provider,
            },
        )

        # set the ttl on the key
        self._redis.expire(key, self._default_ttl_seconds)
        # return success message (the uuid of the key or something)
        raise NotImplementedError

    @staticmethod
    def _encode_vector(embedding: list[float]) -> str:
        # TODO: encode the embedding into bytes that Redis can store
        #  Encode as little-endian float32 bytes to match the FT index's FLOAT32 vector field.
        raise NotImplementedError
