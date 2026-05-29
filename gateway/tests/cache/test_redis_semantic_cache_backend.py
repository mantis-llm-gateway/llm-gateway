from gateway.cache.redis_semantic_cache_backend import RedisSemanticCacheBackend


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
