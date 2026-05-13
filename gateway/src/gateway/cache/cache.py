import hashlib
import re
from typing import Protocol


class CacheClient(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl_seconds: int) -> None: ...


class PromptCache:
    def __init__(self, client: CacheClient, default_ttl_seconds: int = 3600):
        self._client = client
        self._default_ttl_seconds = default_ttl_seconds

    def get(self, prompt: str) -> str | None:
        return self._client.get(self._key(prompt))

    def set(self, prompt: str, response: str, ttl_seconds: int | None = None) -> None:
        # TODO: store response metadata (model, tokens, timestamp) when we add observability
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl_seconds
        self._client.set(self._key(prompt), response, ttl)

    @staticmethod
    def _key(prompt: str) -> str:
        normalized = re.sub(r"\s+", " ", prompt).strip()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class InMemoryCacheClient:
    """In-memory CacheClient for tests. Not thread-safe. TTL is accepted but ignored."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._store[key] = value
