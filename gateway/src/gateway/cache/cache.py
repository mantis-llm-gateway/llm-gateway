import hashlib
import re
from typing import Protocol


class CacheBackend(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl_seconds: int) -> None: ...


class PromptCache:
    """Exact-match prompt cache.

    Callers pass `prompt` (plus optional `model` / `provider`) to `get`/`set` —
    key derivation is internal. Will grow into an exact + semantic orchestrator.
    """

    PREFIX = "prompt:exact:"

    def __init__(self, client: CacheBackend, default_ttl_seconds: int = 3600):
        self._client = client
        self._default_ttl_seconds = default_ttl_seconds

    def get(
        self, *, prompt: str, model: str | None = None, provider: str | None = None
    ) -> str | None:
        """
        Return cached response, or None on miss.
        Backend failures will be raised (contract TBD with Redis adapter).
        """
        key = self._build_exact_key(prompt=prompt, model=model, provider=provider)
        return self._client.get(key)

    # TODO: store response metadata (model, tokens, timestamp) when we add observability.
    # Cached values are raw response strings for now.
    def set(
        self,
        *,
        prompt: str,
        response: str,
        model: str | None = None,
        provider: str | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        key = self._build_exact_key(prompt=prompt, model=model, provider=provider)
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl_seconds
        self._client.set(key, response, ttl)

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
