import pytest
from redis.exceptions import ResponseError

from gateway.cache.redis_semantic_cache_backend import RedisSemanticCacheBackend
from tests.cache.fake_embedder import FakeEmbedder


class FakeIndexRedis:
    """Minimal async Redis stand-in for ensure_index_exists tests.

    Only implements execute_command, optionally raising a configured error
    to simulate FT.CREATE responses from Redis OSS or Valkey.
    """

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.execute_command_calls: list[tuple] = []

    async def execute_command(self, *args) -> None:
        self.execute_command_calls.append(args)
        if self._error is not None:
            raise self._error


def _make_backend(redis) -> RedisSemanticCacheBackend:
    return RedisSemanticCacheBackend(
        redis_client=redis,
        embedder=FakeEmbedder(),
        similarity_threshold=0.8,
        top_k=3,
    )


def test_parses_multiple_matches():
    raw = [
        2,
        "prompt:semantic:abc123def456",
        ["payload", "The answer you crave is 42", "distance", "0.1"],
        "prompt:semantic:def456def999",
        ["payload", "Accordingly, the dolphins ascended.", "distance", "0.4"],
    ]

    expected = [
        {"payload": "The answer you crave is 42", "similarity": 0.9},
        {"payload": "Accordingly, the dolphins ascended.", "similarity": 0.6},
    ]

    assert RedisSemanticCacheBackend._parse_search_results(raw) == expected


def test_parse_search_results_returns_empty_list_when_no_matches():
    raw = [0]
    assert RedisSemanticCacheBackend._parse_search_results(raw) == []


def test_parse_search_results_defaults_to_max_distance_when_distance_missing():
    raw = [
        1,
        "prompt:semantic:abc123",
        ["payload", "Hello"],
    ]

    expected = [{"payload": "Hello", "similarity": 0.0}]

    assert RedisSemanticCacheBackend._parse_search_results(raw) == expected


def test_parse_search_results_decodes_bytes_fields():
    raw = [
        1,
        b"prompt:semantic:abc123",
        [b"payload", b"The answer you crave is 42", b"distance", b"0.1"],
    ]

    expected = [{"payload": "The answer you crave is 42", "similarity": 0.9}]

    assert RedisSemanticCacheBackend._parse_search_results(raw) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        # Redis OSS wording
        "Index already exists",
        # Valkey wording
        "Index idx:semantic in database 0 already exists.",
    ],
)
async def test_ensure_index_exists_swallows_already_exists_errors(message):
    redis = FakeIndexRedis(error=ResponseError(message))
    backend = _make_backend(redis)

    # Should not raise for either Redis OSS or Valkey "already exists" wording.
    await backend.ensure_index_exists()


@pytest.mark.asyncio
async def test_ensure_index_exists_reraises_unrelated_response_errors():
    redis = FakeIndexRedis(error=ResponseError("Something else broke"))
    backend = _make_backend(redis)

    with pytest.raises(ResponseError, match="Something else broke"):
        await backend.ensure_index_exists()
