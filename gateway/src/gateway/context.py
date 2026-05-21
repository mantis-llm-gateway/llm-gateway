from dataclasses import dataclass

from redis.asyncio import Redis

from gateway.engine import ProviderAdaptor
from gateway.models import Config
from gateway.settings import Settings


@dataclass
class AppContext:
    """Process-wide dependencies, built once at startup.

    Holds anything the request path needs that isn't request-scoped:
    settings, clients, caches. Future additions (PromptCache, ProviderAdaptor,
    routing config, orchestrator) go here.
    """

    settings: Settings
    config: Config
    redis: Redis
    adaptor: ProviderAdaptor


def build_context(settings: Settings, config: Config) -> AppContext:
    redis = _build_redis(settings)
    adaptor = ProviderAdaptor()
    return AppContext(settings=settings, config=config, redis=redis, adaptor=adaptor)


def _build_redis(settings: Settings) -> Redis:
    if settings.cache_auth_token:
        return Redis(
            host=settings.cache_endpoint,
            port=settings.cache_port,
            password=settings.cache_auth_token,
            decode_responses=True,
        )
    return Redis(
        host=settings.cache_endpoint,
        port=settings.cache_port,
        decode_responses=True,
    )


async def shutdown_context(ctx: AppContext) -> None:
    """Close clients held by the context. Called from the FastAPI lifespan."""
    await ctx.redis.aclose()
