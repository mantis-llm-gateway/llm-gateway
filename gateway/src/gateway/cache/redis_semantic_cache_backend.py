import string
import uuid
from typing import Any

import numpy as np
import redis
from redis.exceptions import ResponseError

from gateway.cache.embedders import Embedder


# TODO: add tests before calling this in PromptCache constructor
# and working on the exact-match + semantic cache ordering
class RedisSemanticCacheBackend:
    """Semantic cache backed by Redis (RediSearch via redis-stack; ElastiCache + Valkey in prod).

    Stores prompts as vector embeddings keyed on a fresh UUID, with provider/model
    tags for strict filtering at lookup. Lookups return the cached response only
    when the top match clears the similarity threshold.
    """

    # TODO: verify FT.SEARCH, FT.CREATE syntax against ElastiCache w/ Valkey before prod deploy.
    # Will be mostly the same, but minor syntax differences may exist

    PREFIX = "prompt:semantic:"
    REDIS_INDEX_NAME = "idx:semantic"

    # TODO: make configurable from env variables (local) or config file (production)
    DEFAULT_SIMILARITY_THRESHOLD = 0.8
    DEFAULT_TOP_K = 3

    # Used to sanitize model and provider tags when storing and looking up
    ALLOWED_TAG_CHARS = set(string.ascii_letters + string.digits + "_.")

    def __init__(
        self,
        redis_client: redis.Redis,
        embedder: Embedder,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        top_k: int = DEFAULT_TOP_K,
    ):
        self._redis = redis_client
        self._embedder = embedder
        self._similarity_threshold = similarity_threshold
        self._top_k = top_k

        self.ensure_index_exists()

    def ensure_index_exists(self) -> None:
        """Create the FT index if it doesn't already exist.
        Safe to call repeatedly."""
        try:
            self._redis.execute_command(
                "FT.CREATE",
                self.REDIS_INDEX_NAME,
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
                str(self._embedder.DIMENSIONS),
                "DISTANCE_METRIC",
                "COSINE",
                "model",
                "TAG",
                "provider",
                "TAG",
            )
        except ResponseError as e:
            # TODO: this wording may change. Make more robust
            if "Index already exists" not in str(e):
                raise

    def lookup(self, prompt: str, model: str, provider: str) -> str | None:
        """Return a cached response for a semantically similar prompt, or None.

        Embeds the prompt, filters stored entries on (provider, model), and runs
        a top-k cosine-similarity search. Returns the top match's payload if its
        similarity meets `self._similarity_threshold`; otherwise None.
        """
        embedding = self._embedder.embed(prompt)

        # Filter tags must match how values were stored, so sanitize on store and lookup
        sanitized_model = self._sanitize_tag(model)
        sanitized_provider = self._sanitize_tag(provider)

        # Used to pre-filter on provider and model
        # then vector search the remainder by cosine distance.
        query = (
            f"(@provider:{{{sanitized_provider}}} @model:{{{sanitized_model}}})"
            f"=>[KNN {self._top_k} @vector $vec AS distance]"
        )

        # Runs the search, returns [total, key1, [field1, val1, ...], key2, [...], ...]
        # PARAMS binds the encoded vector to $vec in the query
        # DIALECT 2 enables the `=>[KNN ...]` syntax used above
        # Response is limited to 2 fields: "payload" and "distance" (lower = more similar)
        result = self._redis.execute_command(
            "FT.SEARCH",
            self.REDIS_INDEX_NAME,
            query,
            "PARAMS",
            "2",
            "vec",
            self._encode_vector(embedding),
            "RETURN",
            "2",
            "payload",
            "distance",
            "SORTBY",
            "distance",
            "DIALECT",
            "2",
        )

        matches = self._parse_search_results(result)

        if len(matches) > 0 and matches[0]["similarity"] >= self._similarity_threshold:
            # TODO: think about logging the other matches for threshold tuning?
            print(f"Semantic cache hit with similarity: {matches[0]['similarity']}")
            return matches[0]["payload"]
        else:
            print("Semantic cache lookup miss")
            return None

    def store(
        self, prompt: str, response: str, model: str, provider: str, ttl_seconds: int
    ) -> None:
        """Store a prompt/response pair under a fresh UUID key.

        Embeds the prompt (the vector is what later lookups search against) and
        writes a Redis HASH with the vector, response payload, and sanitized
        provider/model tags.
        """
        embedding = self._embedder.embed(prompt)
        key_id = uuid.uuid4().hex
        key = f"{self.PREFIX}{key_id}"

        sanitized_model = self._sanitize_tag(model)
        sanitized_provider = self._sanitize_tag(provider)

        # TODO: add logging for production logs
        # (requires logging config setup at project entry point)
        # logging.info(f"Attempting to store key {key}...")
        print("We're trying to store (`.set`) in the semantic cache now...")

        # Stored as a Redis HASH so vector + response + tags stay co-located.
        self._redis.hset(
            key,
            mapping={
                "vector": self._encode_vector(embedding),
                "payload": response,
                "model": sanitized_model,
                "provider": sanitized_provider,
            },
        )

        print(f"Attempting to store key {key[:25]}... with TTL of {ttl_seconds} seconds")

        self._redis.expire(key, ttl_seconds)

        # TODO: add logging for production logs
        # (requires logging config setup at project entry point)
        # logging.info(f"Stored key {key} with result: {result}")

        print(f"Stored key {key[:25]}... with TTL of {ttl_seconds} seconds\n")

    @staticmethod
    def _encode_vector(embedding: list[float]) -> bytes:
        """Encode as little-endian float32 bytes
        to match the format the Redis vector index expects."""
        return np.array(embedding, dtype="<f4").tobytes()

    @classmethod
    def _sanitize_tag(cls, value: str) -> str:
        """Keep safe chars in RediSearch tag filters; replace unsafe with "_"

        Chars outside ALLOWED_TAG_CHARS (e.g. "-", which FT.SEARCH parses as the negation
        operator) would break TAG filters. Applying the same replacement on store
        and lookup means the query filter matches the sanitized form that was
        actually written to Redis.

        Applied to `model` and `provider` on both `store` and `lookup`.
        """
        return "".join(char if char in cls.ALLOWED_TAG_CHARS else "_" for char in value)

    @staticmethod
    def _parse_search_results(raw: Any) -> list[dict[str, Any]]:
        """Parse FT.SEARCH output into a list of {payload, similarity} dicts.

        Input shape: [total, key1, [field, val, ...], key2, [...], ...]
        RediSearch returns cosine distance; we convert it to similarity (1 - distance)
        so higher = more similar. Returns [] if no results.
        """
        if not raw or raw[0] == 0:
            return []

        matches = []
        # Outer loop: walk `raw` two slots at a time. Each pair is (key_name, fields_list).
        for i in range(1, len(raw), 2):
            fields = raw[i + 1]

            field_map = {}

            # Inner loop: walk each (field_name, value) pair inside this entry's fields.
            for j in range(0, len(fields), 2):
                key = fields[j]
                value = fields[j + 1]
                if isinstance(key, bytes):
                    key = key.decode()
                if isinstance(value, bytes):
                    value = value.decode()
                field_map[key] = value

            # 1.0 used as a safe fallback. Most dissimilar distance.
            distance = float(field_map.get("distance", 1.0))
            matches.append(
                {
                    "payload": field_map.get("payload"),
                    "similarity": 1.0 - distance,
                }
            )
        return matches
