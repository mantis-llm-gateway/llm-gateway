import pytest
from fastapi.testclient import TestClient

from gateway.cache.prompt_cache import PromptCache
from gateway.context import AppContext
from gateway.engine import GuardrailIntervention, StreamResult
from gateway.main import app
from gateway.models import (
    AliasConfig,
    Config,
    PromptCacheConfig,
    RoutingRuleConfig,
    RuleMatchConfig,
    TargetConfig,
)
from gateway.settings import Settings
from tests.cache.in_memory_backends import InMemoryCacheBackend


class FakeAsyncRedis:
    """Minimal async Redis stand-in for handler tests.

    Implements only the methods the handler actually calls today:
    .exists() and .set() (the latter once the executor lands).
    Expand as needed.
    """

    def __init__(self) -> None:
        self._cooldowns: set[str] = set()

    async def exists(self, key: str) -> int:
        return 1 if key in self._cooldowns else 0

    async def set(self, key: str, value, ex: int | None = None) -> None:
        self._cooldowns.add(key)

    async def aclose(self) -> None:
        pass


class FakeAdaptor:
    """ProviderAdaptor stand-in. Configurable response/error for tests."""

    def __init__(self) -> None:
        self.send_request_calls: list[tuple[str, list]] = []
        self.stream_request_calls: list[tuple[str, list]] = []
        self.response: str = "fake response"
        self.stream_response: list[str] = ["fake response"]
        self.error: Exception | None = None
        self.guardrail_intervention: bool = False

    async def send_request(self, model_id: str, messages: list) -> dict | GuardrailIntervention:
        self.send_request_calls.append((model_id, messages))
        if self.error is not None:
            raise self.error

        if self.guardrail_intervention:
            return GuardrailIntervention(response="blocked by guardrail", trace={"reason": "test"})

        return {"response": self.response, "input_tokens": 0, "output_tokens": 0}

    async def stream_request(self, model_id: str, messages: list) -> StreamResult:
        self.stream_request_calls.append((model_id, messages))
        if self.error is not None:
            raise self.error

        result = StreamResult()

        async def chunks():
            if self.guardrail_intervention:
                result._guardrail_info["trace"] = {"reason": "test"}
                return
            for chunk in self.stream_response:
                yield chunk
            result._usage_info["input_tokens"] = 5
            result._usage_info["output_tokens"] = 10

        result._chunks = chunks()
        return result


@pytest.fixture
def fake_redis() -> FakeAsyncRedis:
    return FakeAsyncRedis()


@pytest.fixture
def fake_prompt_cache() -> PromptCache:
    exact = InMemoryCacheBackend()
    return PromptCache(default_ttl_seconds=3600, exact_backend=exact)


@pytest.fixture
def fake_adaptor() -> FakeAdaptor:
    return FakeAdaptor()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(cache_endpoint="fake", cache_port=6379)


@pytest.fixture
def test_config() -> Config:
    return Config(
        aliases={
            "model-a": AliasConfig(provider="anthropic", model="claude-3"),
            "fallback": AliasConfig(provider="openai", model="gpt-4"),
        },
        routing_rules=[
            RoutingRuleConfig(
                id="1",
                name="code",
                match=RuleMatchConfig(name="task-type", value="code_generation"),
                targets=[TargetConfig(alias="model-a", weight=1)],
            ),
        ],
        target_retries=2,
        initial_response_timeout=30,
        default_model="model-a",
        fallbacks=["fallback"],
        cooldown_ttl=60,
        prompt_cache=PromptCacheConfig(ttl_seconds=60, temperature_threshold=0.3),
    )


@pytest.fixture
def test_context(
    test_settings, test_config, fake_redis, fake_adaptor, fake_prompt_cache
) -> AppContext:
    return AppContext(
        settings=test_settings,
        config=test_config,
        redis=fake_redis,
        adaptor=fake_adaptor,
        prompt_cache=fake_prompt_cache,
    )


@pytest.fixture
def client(test_context, monkeypatch):
    # Forces lifespan to load a test Config (with semantic cache off), otherwise
    # build_context calls ensure_index_exists() which makes a real Redis call.
    monkeypatch.setattr("gateway.main._load_config", lambda: test_context.config)

    # Override the lifespan-built context with our fake one.
    # TestClient triggers the lifespan, then we overwrite app.state.context.
    with TestClient(app) as c:
        app.state.context = test_context
        yield c
