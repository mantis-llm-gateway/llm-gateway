import hashlib
import re
from typing import Protocol


class ExactCacheBackend(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl_seconds: int) -> None: ...


class SemanticCacheBackend(Protocol):
    def lookup(self, prompt: str, model: str, provider: str) -> str | None: ...
    def store(
        self, prompt: str, response: str, model: str, provider: str, ttl_seconds: int
    ) -> None: ...


class PromptCache:
    # TODO: Set maxmemory + eviction policy (e.g. allkeys-lfu) in Redis/ElastiCache config
    """Two-tier prompt cache: exact-match with optional semantic fallback.

    Callers pass `prompt`, `model`, `provider` to `get`/`set`; key derivation is internal.
    `get` checks exact first, then semantic on miss. `set` writes to both.
    """

    DEFAULT_TTL_SECONDS = 3600
    PREFIX = "prompt:exact:"

    def __init__(
        self,
        exact_backend: ExactCacheBackend,
        semantic_backend: SemanticCacheBackend | None = None,
        default_ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ):
        self._exact = exact_backend
        self._semantic = semantic_backend
        self._default_ttl_seconds = default_ttl_seconds

    # TODO: return additional related info (model, tokens, timestamp, cache hit/miss boolean etc)
    def get(self, *, prompt: str, model: str, provider: str) -> str | None:
        """
        Return cached response, or None on miss.
        Backend failures will be raised (contract TBD with Redis adapter).
        """
        key = self._build_exact_key(prompt=prompt, model=model, provider=provider)
        print("Trying to do an exact-match cache lookup (`.get`)...")
        hit = self._exact.get(key)
        print(f"Result of the exact-match cache lookup: {hit!r}\n")

        if hit is None and self._semantic is not None:
            print("Trying to do a semantic cache lookup (`.get`)...")
            hit = self._semantic.lookup(prompt=prompt, model=model, provider=provider)
            print(f"Result of the semantic cache lookup: {hit!r}\n")

        return hit

    # TODO: store response metadata (model, tokens, timestamp) when we add observability.
    # Cached values are raw response strings for now.
    def set(
        self,
        *,
        prompt: str,
        response: str,
        model: str,
        provider: str,
        ttl_seconds: int | None = None,
    ) -> None:
        """
        Omit `ttl_seconds` to use the cache's configured default TTL
        Pass an int to override per call.
        """
        key = self._build_exact_key(prompt=prompt, model=model, provider=provider)

        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl_seconds

        self._exact.set(key, response, ttl)

        if self._semantic is not None:
            self._semantic.store(
                prompt=prompt, response=response, model=model, provider=provider, ttl_seconds=ttl
            )

    @classmethod
    def _build_exact_key(cls, *, prompt: str, model: str, provider: str) -> str:
        """
        Builds a key using the class prefix ('prompt:exact:'), provider, model,
        and a hash of the prompt text with whitespace removed
        """
        normalized = re.sub(r"\s+", " ", prompt).strip()
        hashed = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

        provider_and_model = ":".join(cls._sanitize(part) for part in (provider, model))
        return f"{cls.PREFIX}{provider_and_model}:{hashed}"

    @staticmethod
    def _sanitize(string: str | None) -> str:
        """
        Removes all colons from a string
        """
        if not string:
            return "_"
        return string.replace(":", "_")
