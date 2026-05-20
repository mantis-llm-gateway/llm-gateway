from dataclasses import dataclass

from redis.asyncio import Redis

from gateway.settings import Settings


@dataclass
class AppContext:
    """Process-wide dependencies, built once at startup.

    Holds anything the request path needs that isn't request-scoped:
    settings, clients, caches. Future additions (PromptCache, ProviderAdaptor,
    streaming function from Riz, routing config once it's lifted out of main)
    go here.
    """

    settings: Settings
    redis: Redis


def build_context(settings: Settings) -> AppContext:
    redis = _build_redis(settings)
    return AppContext(settings=settings, redis=redis)


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
    await ctx.redis.close()
