import hashlib
import re
from typing import Protocol


class CacheClient(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl_seconds: int) -> None: ...


class PromptCache:
    """Exact-match prompt cache for now.
    This class will become the orchestrator for exact + semantic later."""

    PREFIX = "prompt:exact:"

    # TODO: `prompt` used for now.
    # Later, `model`, `provider`, etc. can be added to build more specific keys
    @classmethod
    def build_exact_key(cls, prompt: str) -> str:
        normalized = re.sub(r"\s+", " ", prompt).strip()
        hashed = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"{cls.PREFIX}{hashed}"

    def __init__(self, client: CacheClient, default_ttl_seconds: int = 3600):
        self._client = client
        self._default_ttl_seconds = default_ttl_seconds

    def get(self, key: str) -> str | None:
        """Return cached response, or None on miss.
        Backend failures will be raised (contract TBD with Redis adapter)."""
        return self._client.get(key)

    # TODO: store response metadata (model, tokens, timestamp) when we add observability.
    # Cached values are raw response strings for now.
    def set(self, key: str, response: str, ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl_seconds
        self._client.set(key, response, ttl)


class InMemoryCacheClient:
    """In-memory CacheClient for tests. TTL is accepted but ignored."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._store[key] = value
