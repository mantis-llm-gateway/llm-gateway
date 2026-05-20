class InMemoryCacheBackend:
    """In-memory ExactCacheBackend for tests. TTL is accepted but ignored."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._store[key] = value


class InMemorySemanticBackend:
    """In-memory SemanticCacheBackend for tests. Records calls for assertions."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str, str], str] = {}
        self.lookup_calls: list[dict] = []
        self.store_calls: list[dict] = []

    def lookup(self, prompt: str, model: str, provider: str) -> str | None:
        self.lookup_calls.append({"prompt": prompt, "model": model, "provider": provider})
        return self._store.get((prompt, model, provider))

    def store(
        self, prompt: str, response: str, model: str, provider: str, ttl_seconds: int
    ) -> None:
        self.store_calls.append(
            {
                "prompt": prompt,
                "response": response,
                "model": model,
                "provider": provider,
                "ttl_seconds": ttl_seconds,
            }
        )
        self._store[(prompt, model, provider)] = response
