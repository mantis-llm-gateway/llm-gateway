from gateway.cache.cache import PromptCache
from gateway.cache.in_memory_client import InMemoryCacheClient


def test_get_returns_none_on_miss():
    cache = PromptCache(client=InMemoryCacheClient())
    key = PromptCache.build_exact_key("never stored")
    assert cache.get(key) is None


def test_set_then_get_round_trips():
    cache = PromptCache(client=InMemoryCacheClient())
    key = PromptCache.build_exact_key("what is the capital of France?")
    cache.set(key, "Paris")
    assert cache.get(key) == "Paris"


def test_build_exact_key_normalizes_whitespace():
    canonical = PromptCache.build_exact_key("hello world")
    assert PromptCache.build_exact_key("hello   world") == canonical
    assert PromptCache.build_exact_key("  hello world  ") == canonical
    assert PromptCache.build_exact_key("hello\tworld") == canonical
    assert PromptCache.build_exact_key("hello\nworld") == canonical


def test_build_exact_key_is_case_sensitive():
    assert PromptCache.build_exact_key("Apple") != PromptCache.build_exact_key("apple")


def test_build_exact_key_includes_prefix():
    key = PromptCache.build_exact_key("anything")
    assert key.startswith("prompt:exact:")


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
    cache.set("any-key", "response")
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
    cache.set("any-key", "response", ttl_seconds=99)
    assert recorder.last_ttl == 99
