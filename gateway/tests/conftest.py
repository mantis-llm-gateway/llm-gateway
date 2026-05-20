# tests/conftest.py  (new file)
import pytest
from fastapi.testclient import TestClient

from gateway.context import AppContext
from gateway.main import app
from gateway.settings import Settings


class FakeAsyncRedis:
    """Minimal async Redis stand-in for handler tests.

    Implements only the methods main.py's handler actually calls:
    .exists() and .set() (the latter once Riz's try_target lands).
    Expand as needed.
    """

    def __init__(self) -> None:
        self._cooldowns: set[str] = set()

    async def exists(self, key: str) -> int:
        return 1 if key in self._cooldowns else 0

    async def set(self, key: str, value, ex: int | None = None) -> None:
        self._cooldowns.add(key)

    async def close(self) -> None:
        pass


@pytest.fixture
def fake_redis() -> FakeAsyncRedis:
    return FakeAsyncRedis()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        cache_endpoint="fake",
        cache_port=6379,
        cooldown_ttl_seconds=60,
    )


@pytest.fixture
def test_context(test_settings, fake_redis) -> AppContext:
    return AppContext(settings=test_settings, redis=fake_redis)


@pytest.fixture
def client(test_context):
    # Override the lifespan-built context with our fake one.
    # TestClient triggers the lifespan, then we overwrite app.state.context.
    with TestClient(app) as c:
        app.state.context = test_context
        yield c
