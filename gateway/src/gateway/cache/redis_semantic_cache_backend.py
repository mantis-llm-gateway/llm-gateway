import logging
import uuid

import numpy as np
import redis
from redis.exceptions import ResponseError

from gateway.cache.embedders import Embedder


class RedisSemanticCacheBackend:
    # TODO: make configurable from env variables (local) or config file (production)
    # TODO: verify FT.SEARCH, FT.CREATE syntax against ElastiCache w/ Valkey before prod deploy.
    # Will be mostly the same, but minor syntax differences may exist
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

    def ensure_index_exists(self) -> None:
        """Create the FT index if it doesn't already exist.
        Safe to call repeatedly. Safe to call repeatedly."""
        try:
            self._redis.execute_command(
                "FT.CREATE",
                "idx:semantic",
                "ON",
                "HASH",
                "PREFIX",
                "1",
                self.PREFIX,
                "SCHEMA",
                "vector",
                "VECTOR",
                "HNSW",
                "6",
                "TYPE",
                "FLOAT32",
                "DIM",
                "1024",
                "DISTANCE_METRIC",
                "COSINE",
                "model",
                "TAG",
                "provider",
                "TAG",
            )
        except ResponseError as e:
            if "Index already exists" not in str(e):
                raise

    def lookup(self, prompt: str, model: str, provider: str) -> str | None:
        # TODO:
        # create embedding of prompt
        # search redis for similar vectors filtered on model and provider
        # given top-k, return the first one (maybe log the others for threshold tuning?)
        raise NotImplementedError

    def store(self, prompt: str, response: str, model: str, provider: str) -> None:
        embedding = self._embedder.embed(prompt)
        key_id = uuid.uuid4().hex
        key = f"{self.PREFIX}{key_id}"

        # Stored as a Redis HASH so vector + response + tags stay co-located.
        logging.info(f"Attempting to store key {key}...")
        result = self._redis.hset(
            key,
            mapping={
                "vector": self._encode_vector(embedding),
                "payload": response,
                "model": model,
                "provider": provider,
            },
        )

        self._redis.expire(key, self._default_ttl_seconds)

        # TODO: remove in prod (useful now for local testing)
        logging.info("Stored key {key} with result:\n", result)

    @staticmethod
    def _encode_vector(embedding: list[float]) -> bytes:
        """Encode as little-endian float32 bytes
        to match the format the Redis vector index expects."""
        return np.array(embedding, dtype="<f4").tobytes()
