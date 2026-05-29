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


class FakeSearchRedis:
    """Minimal async Redis stand-in for lookup tests.

    Returns a canned FT.SEARCH response so we can drive `lookup` without
    standing up real Redis or computing real embeddings. Also records the
    args passed to execute_command so tests can assert command shape.
    """

    def __init__(self, search_response: list) -> None:
        self._search_response = search_response
        self.execute_command_calls: list[tuple] = []

    async def execute_command(self, *args) -> list:
        self.execute_command_calls.append(args)
        return self._search_response


def _make_backend(
    redis,
    *,
    top_k: int = 3,
    similarity_threshold: float = 0.8,
) -> RedisSemanticCacheBackend:
    return RedisSemanticCacheBackend(
        redis_client=redis,
        embedder=FakeEmbedder(),
        similarity_threshold=similarity_threshold,
        top_k=top_k,
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


@pytest.mark.asyncio
async def test_lookup_picks_best_match_when_results_are_out_of_order():
    # FT.SEARCH does not guarantee ascending distance ordering across the result
    # set. Here the first entry is the worse match (distance 0.4 -> similarity 0.6)
    # and the second is the better match (distance 0.1 -> similarity 0.9). lookup
    # must return the second entry's payload, not the first.
    search_response = [
        2,
        "prompt:semantic:worse",
        ["payload", "worse match", "distance", "0.4"],
        "prompt:semantic:better",
        ["payload", "better match", "distance", "0.1"],
    ]
    redis = FakeSearchRedis(search_response=search_response)
    backend = _make_backend(redis)

    result = await backend.lookup(prompt="hello", model="claude-3", provider="anthropic")

    assert result == "better match"


@pytest.mark.asyncio
async def test_lookup_sends_well_formed_ft_search_command():
    # Locks in the shape of the FT.SEARCH command lookup sends to Redis:
    # the command name, target index, the KNN/filter query, PARAMS+vec binding,
    # RETURN fields, LIMIT matched to top_k, and DIALECT 2. Using top_k=5
    # (distinct from the _make_backend default) so the value is visibly threaded
    # through from config into both the KNN clause and LIMIT.
    redis = FakeSearchRedis(search_response=[0])
    backend = _make_backend(redis, top_k=5)

    await backend.lookup(prompt="hello", model="claude-3", provider="anthropic")

    assert len(redis.execute_command_calls) == 1
    args = redis.execute_command_calls[0]

    assert args[0] == "FT.SEARCH"
    assert args[1] == RedisSemanticCacheBackend.REDIS_INDEX_NAME

    # Query string carries the sanitized provider/model filter and the KNN clause
    # tied to top_k. Sanitization replaces "-" with "_" (claude-3 -> claude_3).
    query = args[2]
    assert "@provider:{anthropic}" in query
    assert "@model:{claude_3}" in query
    assert "KNN 5 @vector $vec AS distance" in query

    # PARAMS binds the encoded vector to $vec; the count is the number of
    # name/value pairs that follow (here just one: vec).
    params_index = args.index("PARAMS")
    assert args[params_index : params_index + 3] == ("PARAMS", "2", "vec")
    assert isinstance(args[params_index + 3], bytes)  # encoded vector

    # RETURN limits the response payload to the two fields lookup actually reads.
    return_index = args.index("RETURN")
    assert args[return_index : return_index + 4] == ("RETURN", "2", "payload", "distance")

    # LIMIT must match top_k so we don't silently truncate at the default 10.
    limit_index = args.index("LIMIT")
    assert args[limit_index : limit_index + 3] == ("LIMIT", "0", "5")

    # DIALECT 2 enables the =>[KNN ...] syntax used in the query.
    dialect_index = args.index("DIALECT")
    assert args[dialect_index : dialect_index + 2] == ("DIALECT", "2")
