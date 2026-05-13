from gateway.cache.cache import InMemoryCacheClient, PromptCache


def test_get_returns_none_on_miss():
    cache = PromptCache(client=InMemoryCacheClient())
    assert cache.get("never stored") is None


def test_set_then_get_round_trips():
    cache = PromptCache(client=InMemoryCacheClient())
    cache.set("what is the capital of France?", "Paris")
    assert cache.get("what is the capital of France?") == "Paris"


def test_whitespace_normalization_produces_same_key():
    cache = PromptCache(client=InMemoryCacheClient())
    cache.set("hello   world", "hi there")
    assert cache.get("  hello world  ") == "hi there"
    assert cache.get("hello\tworld") == "hi there"
    assert cache.get("hello\nworld") == "hi there"


def test_case_sensitive_keys():
    cache = PromptCache(client=InMemoryCacheClient())
    cache.set("Apple", "the company")
    assert cache.get("apple") is None
    assert cache.get("Apple") == "the company"


def test_set_uses_default_ttl_when_none_passed():
    class RecordingClient:
        def __init__(self) -> None:
            self.last_ttl: int | None = None

        def get(self, key: str) -> str | None:
            return None

        def set(self, key: str, value: str, ttl_seconds: int) -> None:
            self.last_ttl = ttl_seconds

    recorder = RecordingClient()
    cache = PromptCache(client=recorder, default_ttl_seconds=120)
    cache.set("prompt", "response")
    assert recorder.last_ttl == 120


def test_set_uses_explicit_ttl_when_passed():
    class RecordingClient:
        def __init__(self) -> None:
            self.last_ttl: int | None = None

        def get(self, key: str) -> str | None:
            return None

        def set(self, key: str, value: str, ttl_seconds: int) -> None:
            self.last_ttl = ttl_seconds

    recorder = RecordingClient()
    cache = PromptCache(client=recorder, default_ttl_seconds=120)
    cache.set("prompt", "response", ttl_seconds=99)
    assert recorder.last_ttl == 99
