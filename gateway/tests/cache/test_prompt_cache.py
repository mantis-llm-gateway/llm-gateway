import pytest

from gateway.cache.prompt_cache import PromptCache
from tests.cache.in_memory_backends import InMemoryCacheBackend, InMemorySemanticBackend

EXAMPLE_PROVIDER = "anthropic"
EXAMPLE_MODEL = "opus-4-7"


@pytest.mark.asyncio
async def test_get_returns_none_on_miss():
    cache = PromptCache(exact_backend=InMemoryCacheBackend())
    assert (
        await cache.get(prompt="never stored", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER)
        is None
    )


@pytest.mark.asyncio
async def test_set_then_get_round_trips():
    cache = PromptCache(exact_backend=InMemoryCacheBackend())
    await cache.set(
        prompt="what is the capital of France?",
        response="Paris",
        model=EXAMPLE_MODEL,
        provider=EXAMPLE_PROVIDER,
    )
    assert (
        await cache.get(
            prompt="what is the capital of France?", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER
        )
        == "Paris"
    )


@pytest.mark.asyncio
async def test_whitespace_variants_hit_the_same_entry():
    cache = PromptCache(exact_backend=InMemoryCacheBackend())
    await cache.set(
        prompt="hello world", response="hi", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER
    )
    assert (
        await cache.get(prompt="hello   world", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER)
        == "hi"
    )
    assert (
        await cache.get(prompt="  hello world  ", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER)
        == "hi"
    )
    assert (
        await cache.get(prompt="hello\tworld", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER)
        == "hi"
    )
    assert (
        await cache.get(prompt="hello\nworld", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER)
        == "hi"
    )


@pytest.mark.asyncio
async def test_prompt_is_case_sensitive():
    cache = PromptCache(exact_backend=InMemoryCacheBackend())
    await cache.set(
        prompt="Apple", response="upper", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER
    )
    assert await cache.get(prompt="apple", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER) is None


@pytest.mark.asyncio
async def test_different_models_do_not_share_entries():
    cache = PromptCache(exact_backend=InMemoryCacheBackend())
    await cache.set(prompt="hi", response="from-gpt-4", model="gpt-4", provider="openai")
    assert await cache.get(prompt="hi", model="gpt-4", provider="openai") == "from-gpt-4"
    assert await cache.get(prompt="hi", model="gpt-5.5", provider="openai") is None


@pytest.mark.asyncio
async def test_different_providers_do_not_share_entries():
    cache = PromptCache(exact_backend=InMemoryCacheBackend())
    await cache.set(prompt="hi", response="from-openai", model="gpt-4.5", provider="openai")
    assert await cache.get(prompt="hi", model="gpt-4.5", provider="openai") == "from-openai"
    assert await cache.get(prompt="hi", model="opus-4-7", provider="anthropic") is None


def test_build_exact_key_sanitizes_colons():
    key = PromptCache._build_exact_key(prompt="hi", provider="open:ai", model="gpt:4")
    assert key.startswith("prompt:exact:open_ai:gpt_4:")


@pytest.mark.asyncio
async def test_get_skips_semantic_when_exact_hits():
    exact = InMemoryCacheBackend()
    semantic = InMemorySemanticBackend()
    cache = PromptCache(exact_backend=exact, semantic_backend=semantic)
    await cache.set(
        prompt="hi", response="exact-hit", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER
    )
    semantic.lookup_calls.clear()

    result = await cache.get(prompt="hi", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER)

    assert result == "exact-hit"
    assert semantic.lookup_calls == []


@pytest.mark.asyncio
async def test_get_falls_back_to_semantic_when_exact_misses():
    exact = InMemoryCacheBackend()
    semantic = InMemorySemanticBackend()
    semantic._store[("hi", EXAMPLE_MODEL, EXAMPLE_PROVIDER)] = "semantic-hit"
    cache = PromptCache(exact_backend=exact, semantic_backend=semantic)

    exact_key = PromptCache._build_exact_key(
        prompt="hi", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER
    )
    assert await exact.get(exact_key) is None  # precondition: exact is empty

    result = await cache.get(prompt="hi", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER)

    assert result == "semantic-hit"
    assert len(semantic.lookup_calls) == 1


@pytest.mark.asyncio
async def test_get_returns_none_when_both_miss():
    exact = InMemoryCacheBackend()
    semantic = InMemorySemanticBackend()
    cache = PromptCache(exact_backend=exact, semantic_backend=semantic)

    result = await cache.get(prompt="unseen", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER)

    assert result is None
    assert len(semantic.lookup_calls) == 1  # proves semantic was actually consulted


@pytest.mark.asyncio
async def test_get_works_when_semantic_backend_is_none():
    exact = InMemoryCacheBackend()
    cache = PromptCache(exact_backend=exact, semantic_backend=None)
    assert await cache.get(prompt="unseen", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER) is None


@pytest.mark.asyncio
async def test_set_writes_to_both_backends():
    exact = InMemoryCacheBackend()
    semantic = InMemorySemanticBackend()
    cache = PromptCache(exact_backend=exact, semantic_backend=semantic)

    await cache.set(prompt="hi", response="answer", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER)

    exact_key = PromptCache._build_exact_key(
        prompt="hi", model=EXAMPLE_MODEL, provider=EXAMPLE_PROVIDER
    )
    assert await exact.get(exact_key) == "answer"
    assert semantic.store_calls == [
        {
            "prompt": "hi",
            "response": "answer",
            "model": EXAMPLE_MODEL,
            "provider": EXAMPLE_PROVIDER,
            "ttl_seconds": PromptCache.DEFAULT_TTL_SECONDS,
        }
    ]


@pytest.mark.asyncio
async def test_set_propagates_explicit_ttl_to_semantic():
    exact = InMemoryCacheBackend()
    semantic = InMemorySemanticBackend()
    cache = PromptCache(exact_backend=exact, semantic_backend=semantic)

    await cache.set(
        prompt="hi",
        response="answer",
        model=EXAMPLE_MODEL,
        provider=EXAMPLE_PROVIDER,
        ttl_seconds=99,
    )

    assert semantic.store_calls[0]["ttl_seconds"] == 99
