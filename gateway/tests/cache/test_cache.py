from gateway.cache.cache import PromptCache
from gateway.cache.in_memory_client import InMemoryCacheClient


def test_get_returns_none_on_miss():
    cache = PromptCache(client=InMemoryCacheClient())
    assert cache.get(prompt="never stored") is None


def test_set_then_get_round_trips():
    cache = PromptCache(client=InMemoryCacheClient())
    cache.set(prompt="what is the capital of France?", response="Paris")
    assert cache.get(prompt="what is the capital of France?") == "Paris"


def test_whitespace_variants_hit_the_same_entry():
    cache = PromptCache(client=InMemoryCacheClient())
    cache.set(prompt="hello world", response="hi")
    assert cache.get(prompt="hello   world") == "hi"
    assert cache.get(prompt="  hello world  ") == "hi"
    assert cache.get(prompt="hello\tworld") == "hi"
    assert cache.get(prompt="hello\nworld") == "hi"


def test_prompt_is_case_sensitive():
    cache = PromptCache(client=InMemoryCacheClient())
    cache.set(prompt="Apple", response="upper")
    assert cache.get(prompt="apple") is None


def test_different_models_do_not_share_entries():
    cache = PromptCache(client=InMemoryCacheClient())
    cache.set(prompt="hi", response="from-gpt-4", model="gpt-4")
    assert cache.get(prompt="hi", model="gpt-4") == "from-gpt-4"
    assert cache.get(prompt="hi", model="claude-opus-4-7") is None
    assert cache.get(prompt="hi") is None


def test_different_providers_do_not_share_entries():
    cache = PromptCache(client=InMemoryCacheClient())
    cache.set(prompt="hi", response="from-openai", provider="openai")
    assert cache.get(prompt="hi", provider="openai") == "from-openai"
    assert cache.get(prompt="hi", provider="anthropic") is None


class RecordingClient:
    def __init__(self) -> None:
        self.last_ttl: int | None = None

    def get(self, key: str) -> str | None:
        return None

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self.last_ttl = ttl_seconds


def test_set_uses_default_ttl_when_none_passed():
    recorder = RecordingClient()
    cache = PromptCache(client=recorder, default_ttl_seconds=120)
    cache.set(prompt="anything", response="response")
    assert recorder.last_ttl == 120


def test_set_uses_explicit_ttl_when_passed():
    recorder = RecordingClient()
    cache = PromptCache(client=recorder, default_ttl_seconds=120)
    cache.set(prompt="anything", response="response", ttl_seconds=99)
    assert recorder.last_ttl == 99


def test_build_exact_key_sanitizes_colons():
    key = PromptCache._build_exact_key(prompt="hi", provider="open:ai", model="gpt:4")
    assert key.startswith("prompt:exact:open_ai:gpt_4:")
