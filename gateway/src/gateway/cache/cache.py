import hashlib
import re
from typing import Protocol


class ExactCacheClient(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl_seconds: int) -> None: ...


class SemanticCacheClient(Protocol):
    def lookup(self, prompt: str, model: str, provider: str) -> str | None: ...
    def store(self, prompt: str, response: str, model: str, provider: str) -> None: ...


class PromptCache:
    """Exact-match prompt cache.

    Callers pass `prompt`, `model`, `provider` (required) to `get`/`set`.
    Key derivation is internal.
    """

    PREFIX = "prompt:exact:"

    def __init__(
        self,
        exact_client: ExactCacheClient,
        semantic_client: SemanticCacheClient | None = None,
        default_ttl_seconds: int = 3600,
    ):
        self._exact = exact_client
        self._semantic = semantic_client
        self._default_ttl_seconds = default_ttl_seconds

    # TODO: return additional related info (model, tokens, timestamp, cache hit/miss boolean etc)
    def get(self, *, prompt: str, model: str, provider: str) -> str | None:
        """
        Return cached response, or None on miss.
        Backend failures will be raised (contract TBD with Redis adapter).
        """
        key = self._build_exact_key(prompt=prompt, model=model, provider=provider)
        hit = self._exact.get(key)

        if hit is None and self._semantic is not None:
            # TODO: do a semantic cache search
            pass

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
        key = self._build_exact_key(prompt=prompt, model=model, provider=provider)
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl_seconds
        self._exact.set(key, response, ttl)

        if self._semantic is not None:
            # TODO: add to semantic cache
            pass

    @classmethod
    def _build_exact_key(
        cls, *, prompt: str, model: str | None = None, provider: str | None = None
    ) -> str:
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
