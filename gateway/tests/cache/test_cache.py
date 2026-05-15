from gateway.cache.cache import PromptCache
from gateway.cache.in_memory_backend import InMemoryCacheBackend

EXAMPLE_PROVIDER = "anthropic"
EXAMPLE_MODEL = "opus-4-7"


def test_get_returns_none_on_miss():
    cache = PromptCache(exact_client=InMemoryCacheBackend())
    assert cache.get(prompt="never stored", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER) is None


def test_set_then_get_round_trips():
    cache = PromptCache(exact_client=InMemoryCacheBackend())
    cache.set(
        prompt="what is the capital of France?",
        response="Paris",
        model=EXAMPLE_MODEL,
        provider=EXAMPLE_PROVIDER,
    )
    assert (
        cache.get(
            prompt="what is the capital of France?", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER
        )
        == "Paris"
    )


def test_whitespace_variants_hit_the_same_entry():
    cache = PromptCache(exact_client=InMemoryCacheBackend())
    cache.set(prompt="hello world", response="hi", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER)
    assert cache.get(prompt="hello   world", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER) == "hi"
    assert (
        cache.get(prompt="  hello world  ", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER) == "hi"
    )
    assert cache.get(prompt="hello\tworld", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER) == "hi"
    assert cache.get(prompt="hello\nworld", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER) == "hi"


def test_prompt_is_case_sensitive():
    cache = PromptCache(exact_client=InMemoryCacheBackend())
    cache.set(prompt="Apple", response="upper", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER)
    assert cache.get(prompt="apple", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER) is None


def test_different_models_do_not_share_entries():
    cache = PromptCache(exact_client=InMemoryCacheBackend())
    cache.set(prompt="hi", response="from-gpt-4", model="gpt-4", provider="openai")
    assert cache.get(prompt="hi", model="gpt-4", provider="openai") == "from-gpt-4"
    assert cache.get(prompt="hi", model="gpt-5.5", provider="openai") is None


def test_different_providers_do_not_share_entries():
    cache = PromptCache(exact_client=InMemoryCacheBackend())
    cache.set(prompt="hi", response="from-openai", model="gpt-4.5", provider="openai")
    assert cache.get(prompt="hi", model="gpt-4.5", provider="openai") == "from-openai"
    assert cache.get(prompt="hi", model="opus-4-7", provider="anthropic") is None


class RecordingClient:
    def __init__(self) -> None:
        self.last_ttl: int | None = None

    def get(self, key: str) -> str | None:
        return None

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self.last_ttl = ttl_seconds


def test_set_uses_default_ttl_when_none_passed():
    recorder = RecordingClient()
    cache = PromptCache(exact_client=recorder, default_ttl_seconds=120)
    cache.set(
        prompt="anything", response="response", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER
    )
    assert recorder.last_ttl == 120


def test_set_uses_explicit_ttl_when_passed():
    recorder = RecordingClient()
    cache = PromptCache(exact_client=recorder, default_ttl_seconds=120)
    cache.set(
        prompt="anything",
        response="response",
        model=EXAMPLE_MODEL,
        provider=EXAMPLE_PROVIDER,
        ttl_seconds=99,
    )
    assert recorder.last_ttl == 99


def test_build_exact_key_sanitizes_colons():
    key = PromptCache._build_exact_key(prompt="hi", provider="open:ai", model="gpt:4")
    assert key.startswith("prompt:exact:open_ai:gpt_4:")
