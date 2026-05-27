from dataclasses import dataclass

import boto3
from redis.asyncio import Redis

from gateway.cache.embedders import BedrockEmbedder
from gateway.cache.prompt_cache import PromptCache
from gateway.cache.redis_exact_cache_backend import RedisExactCacheBackend
from gateway.cache.redis_semantic_cache_backend import RedisSemanticCacheBackend
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
    prompt_cache: PromptCache


async def build_context(settings: Settings, config: Config) -> AppContext:
    redis = _build_redis(settings)
    prompt_cache = await _build_prompt_cache(redis, config, settings)
    adaptor = ProviderAdaptor(
        region_name=settings.aws_region,
        guardrail_id=settings.bedrock_guardrail_id,
        guardrail_version=settings.bedrock_guardrail_version,
    )
    return AppContext(
        settings=settings, config=config, redis=redis, adaptor=adaptor, prompt_cache=prompt_cache
    )


def _build_redis(settings: Settings) -> Redis:
    if settings.cache_auth_token:
        return Redis(
            host=settings.cache_endpoint,
            port=settings.cache_port,
            password=settings.cache_auth_token,
            ssl=True,
            decode_responses=True,
        )
    return Redis(
        host=settings.cache_endpoint,
        port=settings.cache_port,
        decode_responses=True,
    )


async def _build_prompt_cache(redis: Redis, config: Config, settings: Settings) -> PromptCache:
    pc = config.prompt_cache
    exact = RedisExactCacheBackend(redis)
    semantic = None

    if pc.semantic is not None:
        embedder = _build_embedder(settings)
        semantic = RedisSemanticCacheBackend(
            redis,
            embedder,
            similarity_threshold=pc.semantic.similarity_threshold,
            top_k=pc.semantic.top_k,
        )

        await semantic.ensure_index_exists()

    return PromptCache(
        default_ttl_seconds=pc.ttl_seconds, exact_backend=exact, semantic_backend=semantic
    )


# TODO: swap boto3 for aioboto3 (async BedrockEmbedder, await in semantic backend etc)
def _build_embedder(settings: Settings) -> BedrockEmbedder:
    bedrock_client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
    return BedrockEmbedder(
        client=bedrock_client,
        embedding_model=settings.bedrock_embedding_model,
        dimensions=settings.bedrock_embedding_dimensions,
    )


async def shutdown_context(ctx: AppContext) -> None:
    """Close clients held by the context. Called from the FastAPI lifespan."""
    await ctx.redis.aclose()
